// Genera ../../catalogo/iconos.json con el interior de cada SVG del juego Lucide de react-icons.
// La app no usa React: la etiqueta {% icono %} pinta estos trazos. Para agregar uno: sumarlo aquí y correr `npm run generar`.
import { readFileSync, writeFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as lu from "react-icons/lu";

const ICONOS = {
  inicio: "LuHouse", catalogo: "LuPackage", carrito: "LuShoppingCart", pedidos: "LuClipboardList", soporte: "LuMessageCircle",
  camion: "LuTruck", crm: "LuUsers", "alerta-frio": "LuThermometerSnowflake", bi: "LuChartColumn", demo: "LuZap", operacion: "LuLayers",
  panel: "LuLayoutDashboard", ventas: "LuHandshake", clientes: "LuContact", atencion: "LuHeadset", embudo: "LuFilter", demanda: "LuHourglass",
  solicitudes: "LuInbox", cobranza: "LuWallet", requerimientos: "LuMessagesSquare", ia: "LuSparkles", usuarios: "LuUserCog", productos: "LuBoxes",
  stock: "LuPackagePlus", ordenes: "LuReceipt", datos: "LuDatabase", sistema: "LuSettings", agregar: "LuPlus", editar: "LuPencil", borrar: "LuTrash2",
  buscar: "LuSearch", activar: "LuCircleCheck", desactivar: "LuBan", avanzar: "LuArrowRight", cancelar: "LuX", volver: "LuArrowLeft",
  externo: "LuExternalLink", territorio: "LuMapPin", categorias: "LuTags", etapas: "LuFlag", estados: "LuListChecks",
};

const salida = {};
for (const [nombre, componente] of Object.entries(ICONOS)) {
  if (!lu[componente]) throw new Error(`react-icons/lu no tiene ${componente}`);
  salida[nombre] = renderToStaticMarkup(createElement(lu[componente])).replace(/^<svg[^>]*>|<\/svg>$/g, "");
}
const destino = new URL("../../catalogo/iconos.json", import.meta.url);
writeFileSync(destino, JSON.stringify(salida, null, 1) + "\n");
const version = JSON.parse(readFileSync(new URL("package.json", import.meta.url))).dependencies["react-icons"];
console.log(`${Object.keys(salida).length} íconos desde react-icons ${version}`);
