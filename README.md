# Titan Maintenance SaaS

MVP B2B local para gestionar órdenes de mantenimiento de equipos simulados. Permite separar registros por empresa demo, priorizar trabajos y seguir su estado. La elección de empresa sirve para enseñar el flujo; no es autenticación ni aislamiento de seguridad para producción.

## Ejecutar

Requiere Python 3.10 o superior, sin dependencias externas.

```powershell
python app.py
```

Abre `http://127.0.0.1:8090`. SQLite guarda los registros en `maintenance.sqlite3`.

## Funciones

- Crear órdenes con código de equipo, descripción, prioridad y fecha objetivo.
- Consultar órdenes de una empresa demo y filtrarlas por estado.
- Avanzar la orden entre `open`, `in_progress` y `closed`.
- Eliminar registros de la demo.
- API JSON en `/api/orders`; usa `X-Tenant-ID` con `demo-north` o `demo-south`.

## Límite de seguridad

Los tenants son identificadores de demostración seleccionados desde la interfaz. No hay inicio de sesión, autorización ni control de acceso real. No alojes datos sensibles ni uses la aplicación para coordinar mantenimiento real.

## Licencia

MIT.
