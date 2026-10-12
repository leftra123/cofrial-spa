# 4a. Diagrama de arquitectura cloud

> Rúbrica H1-D3 (Logrado): diagrama **profesional** y conectado con la realidad del caso.

## Elementos que debe mostrar
- [ ] Región y zona(s) de disponibilidad
- [ ] VPC con su CIDR
- [ ] Subred pública: EC2 web/backend (e-commerce + CRM + API)
- [ ] Subred para el nodo IoT: EC2 con Docker (contenedores = camiones simulados)
- [ ] Subredes privadas: RDS (DB subnet group)
- [ ] Internet Gateway y tablas de ruteo
- [ ] Security Groups y qué puertos permiten
- [ ] Herramienta BI y de dónde lee
- [ ] API de IA externa (fuera de AWS)
- [ ] Actores: cliente B2B, cliente B2C, vendedor, despachador, gerencia

## Herramienta
Iconos oficiales de AWS (draw.io / diagrams.net tiene la librería AWS). Exportar a PNG/SVG en `informe/img/`.

**Decisión:** se usa draw.io (diagrams.net) por ser gratuito, traer la librería oficial de íconos AWS y guardar el diagrama como archivo `.drawio` editable que se versiona en git. Registrada en `informe/08-herramientas.md`.

![Arquitectura cloud del prototipo](img/arquitectura-cloud.drawio.png)

## Estado
Borrador v0.1 generado con la skill `aws-architecture-diagram` (prueba de herramientas).
- Archivo editable: `informe/img/arquitectura-cloud.drawio` (se abre en draw.io / diagrams.net).
- Se regenera con `python3 informe/img/generar-arquitectura-cloud.py` desde la raíz del repo.
- PNG exportado: `informe/img/arquitectura-cloud.drawio.png` (con el XML embebido, se puede reabrir y editar en draw.io). Comando: `drawio -x -f png -e -b 10 -s 1 -o informe/img/arquitectura-cloud.drawio.png informe/img/arquitectura-cloud.drawio`.
- Pendiente: validar CIDR y tamaños de instancia con el equipo y cruzar con la decisión D-07 de `docs/decisiones.md`.
- Cubre: región, VPC con CIDR, subred pública web, subred pública IoT, subredes privadas (RDS y reserva en 2 AZ), Internet Gateway, tablas de ruteo, Security Groups, EC2 backend con Grafana, EC2 IoT con Docker, RDS, IA externa y los cinco actores.

## Notas del equipo
