# Base de Conocimiento — TechNova (SaaS de gestión de proyectos)

TechNova es una plataforma SaaS para gestionar proyectos, tareas y colaboración
en equipo. Esta base de conocimiento describe sus funcionalidades principales.

## Conceptos básicos
- **Espacio de trabajo (workspace):** contenedor principal de una organización.
- **Proyecto:** agrupa tareas, tableros y documentos de un objetivo.
- **Tarea:** unidad de trabajo con responsable, fecha límite, etiquetas y estado.
- **Subtarea:** desglose de una tarea en pasos más chicos, con su propio responsable.
- **Tablero (board):** vista Kanban de las tareas por estado.
- **Hito (milestone):** fecha clave que agrupa entregables de un proyecto.

## Planes disponibles
TechNova ofrece cinco planes. El detalle completo está en `comercial/planes_y_precios.xlsx`
y `comercial/comparativa_planes.csv`.

- **Free (0 USD/usuario/mes):** para equipos que recién empiezan. Hasta 5 usuarios,
  3 proyectos, 1 GB de almacenamiento y vistas Kanban y Lista.
- **Starter (5 USD/usuario/mes):** equipos pequeños. Hasta 15 usuarios, 20 proyectos,
  10 GB, vista Calendario y soporte por email.
- **Pro (9 USD/usuario/mes):** equipos en crecimiento. Usuarios ilimitados, 50 GB,
  vistas Gantt, acceso a la API y todas las integraciones.
- **Business (18 USD/usuario/mes):** empresas con varios equipos. 200 GB, roles
  personalizados, reportes avanzados, registros de auditoría y soporte por email + chat.
- **Enterprise (precio personalizado):** grandes organizaciones. Almacenamiento
  ilimitado, SSO/SAML incluido, SLA del 99.95%, soporte dedicado 24/7 y un CSM asignado.

Con el pago anual los planes de pago tienen ~17% de descuento (se pagan 10 meses por año).

## Funcionalidades clave
### Tableros y vistas
TechNova ofrece vistas **Kanban, Lista, Calendario, Gantt (cronograma) y Carga de
trabajo**. Cada usuario puede guardar vistas personalizadas, filtros y agrupaciones.
La vista Gantt está disponible desde el plan Pro.

### Automatizaciones
Permite crear reglas tipo *"cuando una tarea pasa a Hecho, notificar al responsable"*
o *"cuando se acerca la fecha límite, recordar al equipo"*. Cada plan tiene un límite
de automatizaciones mensuales (Free 50, Starter 500, Pro 2000, Business 10000,
Enterprise ilimitado).

### Seguimiento del tiempo y reportes
Se puede registrar el tiempo dedicado a cada tarea y generar reportes de avance,
carga por persona y cumplimiento de fechas. Los reportes avanzados y de BI están
disponibles desde el plan Business.

### Integraciones
Se integra con **Slack, Google Drive, GitHub y Zapier**. La configuración técnica de
las integraciones y la API pública está documentada en `datos/integraciones_api.json`.

### Roles y permisos
- **Owner:** control total del workspace y la facturación.
- **Admin:** gestiona miembros, proyectos y configuración de seguridad.
- **Miembro:** crea y edita tareas.
- **Invitado:** acceso de solo lectura a proyectos específicos.
- **Roles personalizados:** desde el plan Business se pueden definir roles a medida.

### Seguridad
- Verificación en dos pasos (2FA) en todos los planes.
- Inicio de sesión único (SSO/SAML): add-on en Business, incluido en Enterprise.
- Datos cifrados en tránsito (TLS) y en reposo (AES-256).
- Registros de auditoría (quién hizo qué) en Business y Enterprise.

### Aplicaciones móviles
TechNova tiene apps para iOS y Android con notificaciones push, disponibles en todos
los planes.

## Buenas prácticas
- Usa etiquetas consistentes para poder filtrar entre proyectos.
- Archiva los proyectos cerrados en lugar de eliminarlos, para conservar el historial.
- Activa la autenticación en dos pasos (2FA) desde la configuración de seguridad.
- Usa plantillas de proyecto para estandarizar flujos que se repiten.
- Revisá los reportes de carga de trabajo para evitar sobrecargar al equipo.
