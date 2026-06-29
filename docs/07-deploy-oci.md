# Issue #7 — Deploy en la nube (OCI)

Publicar a Techie (TechNova) de forma estable y reproducible en **Oracle Cloud
Infrastructure**, contenerizado con Docker y desplegado en **OCI Container
Instances** (servicio serverless de contenedores), con la imagen publicada en
**OCI Container Registry (OCIR)** desde un pipeline de **CI/CD** (GitHub Actions).

> Cumple el requisito del issue de usar al menos un servicio de OCI: se usan
> **OCIR** (registry) y **Container Instances** (cómputo).

---

## 1. Arquitectura del deploy

```
GitHub (push a main)
   │  GitHub Actions (.github/workflows/deploy-ocir.yml)
   ▼
build de la imagen Docker ──> push a OCIR  (<region>.ocir.io/<namespace>/techie-asistente)
                                   │
                                   ▼
                        OCI Container Instance  (puerto 8000, IP pública)
                                   │  COHERE_API_KEY desde OCI Vault
                                   ▼
                        Cohere API (embeddings + rerank + generación)
```

Decisiones (ver también el contexto del proyecto):
- **Imagen self-contained**: el corpus (`data/documents/`) y el índice **Chroma**
  (`chroma_db/`) se hornean en la imagen (son ~1.5 MB y de solo lectura). El
  contenedor queda **stateless** → ideal para Container Instances.
- **Embeddings/rerank/generación por API (Cohere)**: no se carga ningún modelo
  pesado en el contenedor; la imagen pesa ~800 MB y arranca rápido.
- **Logs/feedback** (`data/logs`, `data/feedback`) son efímeros en Container
  Instances. Su centralización en la nube es parte del **issue #8**.

## 2. La imagen Docker

`Dockerfile` (en la raíz): `python:3.12-slim`, instala `requirements.txt`, copia
`src/`, `data/documents/` y `chroma_db/`, corre como usuario no-root y expone el
puerto 8000 con `python -m rag serve`. Incluye `HEALTHCHECK` contra `/api/health`.

### Probar en local
```bash
docker build -t techie-asistente:local .
docker run --rm -p 8000:8000 --env-file .env techie-asistente:local
# o, más simple:
COHERE_API_KEY=... docker compose up --build
```
Abrir http://localhost:8000. Verificado: imagen ~817 MB, contenedor `healthy`,
respuestas reales con fuentes y sugerencias.

## 3. Publicar la imagen en OCIR (manual, una vez)

Prerrequisitos: cuenta OCI, una **Auth Token** del usuario (User Settings → Auth
Tokens) y el **namespace** del tenancy (`oci os ns get` o consola → Object Storage).

```bash
# region key: iad (Ashburn), scl (Santiago), etc. -> <key>.ocir.io
docker login iad.ocir.io -u '<namespace>/<usuario>' -p '<auth-token>'

IMG=iad.ocir.io/<namespace>/techie-asistente
docker tag techie-asistente:local $IMG:latest
docker push $IMG:latest
```
Si el usuario está en un dominio de identidad: `-u '<namespace>/<dominio>/<usuario>'`.

## 4. CI/CD (automático)

`.github/workflows/deploy-ocir.yml` construye y publica la imagen en cada push a
`main`. Configurar en GitHub (Settings → Secrets and variables → Actions):

| Secret | Valor |
|---|---|
| `OCIR_REGION` | host del registry, ej. `iad.ocir.io` |
| `OCIR_NAMESPACE` | namespace del tenancy |
| `OCIR_USERNAME` | `<usuario>` (o `<dominio>/<usuario>`) |
| `OCIR_TOKEN` | Auth Token del usuario |

La imagen queda etiquetada `:latest` y `:<sha>` para poder hacer rollback.

## 5. Crear la Container Instance

Consola: **Developer Services → Container Instances → Create**.
- **Image**: `iad.ocir.io/<namespace>/techie-asistente:latest` (registry privado →
  agregar credenciales de OCIR / vault secret con el Auth Token).
- **Shape**: la más chica (1 OCPU / 4 GB alcanza de sobra).
- **Networking**: una VCN con subred pública; asignar **IP pública**.
- **Port**: el contenedor escucha en **8000**.
- **Environment variables**: `COHERE_API_KEY` (idealmente referenciando un secreto
  de **OCI Vault**, ver §6).

Equivalente por CLI (resumido):
```bash
oci container-instances container-instance create \
  --compartment-id <compartment-ocid> \
  --availability-domain <AD> \
  --shape CI.Standard.E4.Flex \
  --shape-config '{"ocpus":1,"memoryInGBs":4}' \
  --containers '[{"imageUrl":"iad.ocir.io/<ns>/techie-asistente:latest",
                  "environmentVariables":{"COHERE_API_KEY":"<o-via-vault>"}}]' \
  --vnics '[{"subnetId":"<subnet-ocid>","isPublicIpAssigned":true}]'
```
Para publicar la nueva imagen tras un push, recrear/reiniciar la instancia
(esbozo opcional en el workflow). Healthcheck del orquestador: `GET /api/health`.

## 6. Red, seguridad y secretos

- **VCN / Security List**: permitir ingreso TCP al puerto de la app (8000), o
  poner un **Load Balancer / API Gateway** delante en 443 (TLS) y enrutar a 8000.
- **OCI Vault**: guardar `COHERE_API_KEY` como secreto y referenciarlo en la
  Container Instance en vez de texto plano. La key **nunca** va en la imagen ni en
  el repo (`.env` está en `.gitignore` y en `.dockerignore`).
- Contenedor **no-root** (uid 10001) y CORS abierto solo para la demo.

## 7. Actualizar el corpus

Como el índice viaja en la imagen, actualizar documentos = reconstruir:
1. Cambiar/agregar archivos en `data/documents/`.
2. `python -m rag ingest` (reindexa solo lo que cambió en `chroma_db/`).
3. Commit/push → CI publica la imagen nueva → recrear la Container Instance.

## 8. Alternativas y siguientes pasos

- **Cómputo**: una **Compute VM Always Free** con `docker compose up -d` es una
  opción aún más barata; **OKE (Kubernetes)** sería para escala/HA.
- **Persistencia**: para escribir feedback/logs de forma durable, montar **Object
  Storage** o migrar el índice a **Autonomous Database 23ai (AI Vector Search)**.
- **Observabilidad** (issue #8): enviar los JSONL a **OCI Logging** y armar
  paneles de métricas; registrar versiones de modelo y prompt.
