# Base de Conocimiento — TechNova (SaaS de gestión de proyectos)

TechNova es una plataforma SaaS para gestionar proyectos, tareas y colaboración
en equipo. Esta base de conocimiento describe sus funcionalidades principales.

## Conceptos básicos
- **Espacio de trabajo (workspace):** contenedor principal de una organización.
- **Proyecto:** agrupa tareas, tableros y documentos de un objetivo.
- **Tarea:** unidad de trabajo con responsable, fecha límite, etiquetas y estado.
- **Tablero (board):** vista Kanban de las tareas por estado.

## Funcionalidades clave
### Tableros y vistas
TechNova ofrece vistas **Kanban, Lista, Calendario y Gantt**. Cada usuario puede
guardar vistas personalizadas y filtros.

### Automatizaciones
Permite crear reglas tipo *"cuando una tarea pasa a Hecho, notificar al responsable"*.
Cada plan tiene un límite de automatizaciones mensuales (ver Planes y Precios).

### Integraciones
Se integra con Slack, Google Drive, GitHub y Zapier. La configuración técnica de
las integraciones está documentada en `datos/integraciones_api.json`.

### Roles y permisos
- **Owner:** control total del workspace y la facturación.
- **Admin:** gestiona miembros y proyectos.
- **Miembro:** crea y edita tareas.
- **Invitado:** acceso de solo lectura a proyectos específicos.

## Buenas prácticas
- Usa etiquetas consistentes para poder filtrar entre proyectos.
- Archiva los proyectos cerrados en lugar de eliminarlos, para conservar el historial.
- Activa la autenticación en dos pasos (2FA) desde la configuración de seguridad.
