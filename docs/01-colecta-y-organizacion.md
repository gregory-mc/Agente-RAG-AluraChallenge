# Issue #1 — Colecta y organización de documentos

Este documento define cómo se recolectan y organizan los documentos internos que
alimentarán al agente. Es la base de todo el proyecto: si entran documentos de mala
calidad o desordenados, las respuestas del agente también lo serán.

> **Empresa del proyecto:** TechNova (ficticia), un SaaS de gestión de proyectos y
> colaboración para equipos.

---

## 1. Mapeo de fuentes

En una empresa real los documentos están dispersos en varias herramientas. Para este
proyecto se definió de dónde proviene cada categoría:

| Fuente | Tipo de contenido |
|---|---|
| Google Drive / Notion | Base de conocimiento del producto, FAQ, onboarding |
| Sitio web y panel de ayuda | FAQ pública, términos de uso |
| Sistema de facturación | Planes, precios y comparativas |
| Repositorio de la API | Documentación técnica de integraciones |
| Carpeta del área Legal | Política de privacidad, términos de uso |

Todos los documentos seleccionados se centralizan en este repositorio, dentro de
`data/documents/`, que es la **única fuente de verdad** para la ingesta.

## 2. Categorías de negocio

Los documentos se organizan en carpetas; **cada subcarpeta de `data/documents/` es una
categoría** (dominio). El nombre de la carpeta se guarda luego como metadato.

| Categoría (carpeta) | Descripción |
|---|---|
| `producto/` | Cómo funciona la plataforma: base de conocimiento y onboarding |
| `soporte/` | Atención al cliente: preguntas frecuentes |
| `comercial/` | Planes, precios y comparativas |
| `legal/` | Privacidad, términos y condiciones |
| `datos/` | Documentación técnica: API e integraciones |

## 3. Curaduría de calidad

Reglas aplicadas para mantener el corpus sano:

- Una sola versión vigente por documento (se eliminan las desactualizadas).
- Nombres de archivo claros y descriptivos.
- Solo formatos soportados (ver inventario).
- Se evita información duplicada entre categorías.

## 4. Responsables por categoría

Cada categoría tiene un área responsable de mantener sus documentos al día:

| Categoría | Responsable |
|---|---|
| `producto/` | Equipo de Producto |
| `soporte/` | Equipo de Soporte / Customer Success |
| `comercial/` | Equipo Comercial |
| `legal/` | Área Legal |
| `datos/` | Equipo de Datos / Plataforma |

## 5. Permisos de acceso

El agente está pensado para **todos los colaboradores** de la empresa, por lo que el
contenido cargado es de acceso interno general (no se cargan documentos confidenciales
ni datos personales). Clasificación usada:

- **Público:** puede verlo cualquiera, incluso fuera de la empresa (ej. términos de uso,
  política de privacidad, FAQ).
- **Interno:** visible para todos los colaboradores (ej. base de conocimiento, planes).

No se incluye material **Confidencial/Restringido** en este corpus.

## 6. Proceso de ingesta inicial

1. Colocar cada documento en la carpeta de su categoría dentro de `data/documents/`.
2. Verificar que el formato esté soportado.
3. (Siguiente etapa — issue #2) extraer el texto y dividirlo en fragmentos.
4. (Siguiente etapa — issue #3) generar embeddings e indexar en la base vectorial.

---

## Inventario de documentos

| Documento | Categoría | Formato | Clasificación | Responsable |
|---|---|---|---|---|
| `producto/base_conocimiento.md` | producto | Markdown | Interno | Producto |
| `producto/onboarding_producto.pptx` | producto | PowerPoint | Interno | Producto |
| `soporte/faq_soporte.html` | soporte | HTML | Público | Soporte |
| `comercial/planes_y_precios.xlsx` | comercial | Excel | Interno | Comercial |
| `comercial/comparativa_planes.csv` | comercial | CSV | Interno | Comercial |
| `legal/politica_privacidad.pdf` | legal | PDF | Público | Legal |
| `legal/terminos_de_uso.docx` | legal | Word | Público | Legal |
| `datos/integraciones_api.json` | datos | JSON | Interno | Datos |

**Cobertura de formatos:** PDF, Word, Excel, PowerPoint, Markdown, CSV, JSON y HTML
— los 8 formatos pedidos por el desafío.
