Para que el equipo y quienes evalúen puedan probar el prototipo en línea sin trámites, las cuentas de demostración usan correos simples y una misma clave de fácil uso. Son datos ficticios en un sistema académico que se mantiene encendido solo durante las pruebas del curso. Las claves de la infraestructura (AWS, base de datos y servicios de inteligencia artificial) no se publican y se guardan fuera del repositorio.

**Tabla 1**
*Cuentas de prueba del prototipo y lo que permite probar cada una*

| Cuenta | Rol | Qué permite probar |
|---|---|---|
| `eric@cofrial.cl` | Administrador (equipo) | Todo el sistema; en la demostración arma el despacho y revisa la ruta |
| `felipe@cofrial.cl` | Cliente institucional (B2B) | Compra con la lista institucional en neto, orden de compra y IVA desglosado |
| `sergio@cofrial.cl` | Cliente particular (B2C) | Compra con precios al público y sigue su pedido en el mapa |
| `admin@cofrial.cl` | Administrador | Todo el sistema, incluida la administración de datos (`/admin/`) |
| `gerencia@cofrial.cl` | Gerencia | CRM de todos los vendedores, indicadores, flota y alertas de frío |
| `vendedora@cofrial.cl` | Vendedora | Embudo comercial, clientes y requerimientos propios |
| `vendedor2@cofrial.cl` | Vendedor | Lo mismo que la vendedora, con su propia cartera |
| `despacho@cofrial.cl` | Despachador | Flota, armado de despachos con ruta sugerida y alertas de frío |
| `abastecimiento@hospital.test` | Cliente institucional (B2B) | Lista de precios institucional en neto, orden de compra y repetir el último pedido |
| `ana@correo.test` | Cliente particular (B2C) | Compra con precios al público, seguimiento del pedido y avisos de stock |

*Nota.* La clave de todas las cuentas es `123456`. Un cliente particular nuevo puede crear su propia cuenta en la página de registro con su RUT, su correo y una dirección de entrega. Elaboración propia.

Para recorrer el flujo completo, se sugiere comprar con la cuenta de un cliente, entrar como despachador para asignar el pedido a un camión y revisar la ruta sugerida, y volver a la cuenta del cliente para seguir el camión y su temperatura. Si un producto está sin stock, el cliente puede pedir un aviso para cuando haya al menos la cantidad que necesita, y el equipo comercial ve esa demanda en el CRM.
