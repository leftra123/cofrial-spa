# Guía de pruebas sobre la instalación en AWS (en orden)

Para quien reciba el traspaso (Sergio) y para ensayar la defensa. Cada paso dice qué hacer, qué debe pasar y qué exigencia de la rúbrica del Hito 2 respalda. **Si algo no pasa como se indica, anotarlo tal cual (pantalla y hora) y avisar.**

## Direcciones

| Qué | Dirección |
|---|---|
| Aplicación | http://34.204.121.79 |
| Estado de salud | http://34.204.121.79/salud/ (debe responder `{"estado": "ok"}`) |
| Tablero de BI (Grafana) | http://34.204.121.79:3000 (se ve sin cuenta; para editar: usuario `admin` y la clave de Grafana) |

La IP es elástica: no cambia al reiniciar el laboratorio. **Las instancias están en la cuenta del laboratorio de Eric**: desde otra cuenta solo se prueban estas direcciones web. Si el laboratorio de Eric está apagado (se apaga a las 4 horas), nada responde hasta que Eric pulse "Start Lab" y espere unos minutos.

## Usuarios de prueba

Todos usan **la misma clave de demostración**. No está en el repositorio: está en `aws/.estado/secretos.env` (variable `DEMO_PASSWORD`) en el computador de Eric. Compartirla por mensaje directo o gestor de contraseñas, **nunca** por GitHub ni Trello.

| Usuario | Rol | Sirve para probar |
|---|---|---|
| `abastecimiento@hospital.test` | Cliente institucional (B2B), Hospital Regional de Temuco | Lista de precios institucional, orden de compra obligatoria, pedidos |
| `compras@supersur.test` | Cliente institucional (B2B), Supermercados del Sur | Segundo cliente B2B con otro vendedor |
| `ana@correo.test` | Cliente público (B2C), Ana Pérez | Precio público, Soporte con IA |
| `vendedora@cofrial.test` | Vendedora (cartera: Hospital) | CRM, embudo, ficha de cliente; no ve la cartera ajena |
| `vendedor2@cofrial.test` | Vendedor (cartera: Supermercados del Sur) | Permisos entre vendedores |
| `gerente@cofrial.test` | Gerencia | Lee todo, no modifica |
| `despachador@cofrial.test` | Despachador | Solo alertas de frío y flota |
| `admin` | Administrador | Todo, incluida la flota y `/admin/` |

## Pruebas, en este orden

**A. Base (1 a 3)**
1. **Salud.** Abrir `/salud/`. Debe decir `ok`. *(D1: la aplicación corre y está conectada.)*
2. **Catálogo sin sesión.** Abrir `/` y `/catalogo/`: se ven productos y precios, el menú muestra solo Inicio y Catálogo. *(D2)*
3. **Rutas protegidas.** Sin sesión, abrir `/pedidos/` y `/crm/`: lleva a la pantalla de entrar.

**B. E-commerce B2B y B2C (4 a 8)** *(D2)*
4. Entrar como `ana@correo.test` (B2C). Anotar el precio de un producto del catálogo.
5. Agregar el producto al carrito, cambiar la cantidad a 2 y generar la orden. Debe aparecer "Orden N recibida" y su detalle con la línea de tiempo del envío.
6. Entrar como `abastecimiento@hospital.test` (B2B). **El mismo producto debe tener otro precio** (lista institucional).
7. Generar una orden: **debe exigir el número de orden de compra**. Probar enviarlo vacío (debe rechazar) y luego con uno cualquiera.
8. En "Mis pedidos" deben aparecer las órdenes del cliente con sus estados y las pestañas con contador. Cancelar una orden recién creada y comprobar que el stock se repone (el catálogo vuelve a mostrarlo).

**C. CRM (9 a 13)** *(D2)*
9. Entrar como `vendedora@cofrial.test`. En `/crm/clientes/` abrir el Hospital: **debe verse la orden web recién creada** en su ficha.
10. Crear un prospecto nuevo (`/crm/prospectos/nuevo/`). Debe quedar en la primera etapa del embudo.
11. Intentar pasarlo a "Contactado" sin registrar una interacción: **debe rechazarlo**. Registrar una interacción y repetir: ahora sí.
12. Entrar como `vendedor2@cofrial.test`: no debe ver la ficha del Hospital ni el prospecto de la otra vendedora (404).
13. Entrar como `gerente@cofrial.test`: ve el panel con ventas por canal, pero **no puede** crear prospectos (403 con la pantalla de "sin acceso").

**D. Cadena de frío e IoT (14 a 17)** *(D3, D4)*
14. Entrar como `admin` y abrir `/flota/`: tres camiones con temperatura, combustible y última lectura.
15. Dejar la pantalla abierta 15 segundos: **la hora de "Última lectura" y la temperatura deben cambiar solas** (llegan lecturas cada 5 segundos). Aparece "En vivo · cada 5 s".
16. Si algún camión muestra **"Ruptura de frío"**, abrir `/crm/alertas/` como `despachador@cofrial.test`: debe listar los pedidos afectados. (La ruptura es aleatoria y poco frecuente; si no ocurre, no es un fallo.)
17. Como `admin`, abrir `/api/flota/`: debe devolver JSON con los camiones y la última lectura (campos `temp_camara`, `lat`, `long`, `combustible_pct`, `alerta_ruptura_frio`).

**E. Tablero de BI (18 a 19)** *(D4)*
18. Abrir Grafana (`:3000`). **Esperar hasta 15 segundos la primera vez.** Deben verse: ventas del período, pedidos, alertas, ventas por canal, temperatura por camión y el mapa de la flota.
19. Hacer una compra nueva como B2B y otra como B2C y esperar 5 a 10 segundos: **las ventas y el gráfico "Ventas por canal" deben cambiar** con ambos canales. *(Cruce ventas contra alertas de frío.)*

**F. IA (20 a 22)** *(D5)*
20. Entrar como `ana@correo.test`, ir a **Soporte** y enviar: asunto "Pedido llegó caliente", texto "La carga llegó con la temperatura muy alta y rechazamos las cajas". Tarda unos 6 segundos. Debe decir que la derivó a **«Reclamo por temperatura»**.
21. Entrar como `vendedora@cofrial.test` y abrir `/crm/requerimientos/`: el requerimiento aparece **clasificado**, con la categoría y el distintivo "IA 0,9x" o "IA 1,00".
22. **No tocar** el requerimiento "Mi pedido llegó tibio" (cliente Supermercados del Sur): está **sin clasificar a propósito**, para clasificarlo en vivo con **"Clasificar con IA"** durante la defensa. Si ya se clasificó por error, enviar uno parecido desde Soporte con otro cliente.

**G. Permisos y errores (23 a 24)**
23. Como cliente (`ana@`), abrir `/crm/` y `/flota/`: pantalla de "No puedes ver esta sección" con el menú del sitio (403), no una página en blanco. El menú del cliente no muestra CRM, Flota ni Administración.
24. Abrir `/pedidos/99999/`: pantalla "No encontramos esa página" (404).

**H. Resiliencia (25 a 26)** *(D1: estable y persistente)*
25. **IA apagada** (solo se puede hacer en local, no en AWS sin acceso a la instancia): con `GEMINI_API_KEY` vacía, enviar un requerimiento: se guarda "sin clasificar" y el portal responde normal. Las pruebas automáticas lo cubren (`python manage.py test crm`).
26. **Apagado y encendido del laboratorio** (lo hace Eric): al terminar la sesión del laboratorio y volver a iniciarla, la aplicación, el IoT y Grafana deben volver solos en unos minutos y la IP debe ser la misma.

## Pruebas automáticas (sin AWS)

Con una base PostgreSQL local y el entorno de `aws/README.md`:

```bash
cd web && python manage.py test        # 57 pruebas, todas deben pasar
```

(No definir `DEMO_PASSWORD` en el entorno al correrlas, o fallan las de inicio de sesión.)

## Si Sergio quiere su propia instalación

Cualquier integrante puede crear una réplica en **su** laboratorio con `bash aws/provision.sh` (ver `aws/README.md`): necesita las credenciales de su Learner Lab (AWS Details → AWS CLI → Show) y, opcionalmente, su propia clave gratuita de Gemini. Cada instalación es independiente y tiene sus propias claves en `aws/.estado/`.
