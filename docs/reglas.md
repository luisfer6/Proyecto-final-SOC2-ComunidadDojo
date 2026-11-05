# Detecciones, hipótesis y límites

Versión del motor: **1.0.0**. Las reglas son implementaciones propias verificables
en `app/analysis.py`; no se presentan como reglas Sigma desplegadas ni como un
resultado validado en Microsoft Sentinel.

| Regla | Selección / agrupación | Criticidad | Falso positivo y dato discriminante |
|---|---|---|---|
| AUTH-01 | Security 4625, ≥5 fallos/10 min, mismo host/IP/reloj; ventanas móviles solapadas se unen | Alto | Servicio mal configurado; códigos de fallo y dueño de la cuenta |
| AUTH-02 | Security 4624 posterior a ≥3 fallos/15 min; mismo host, cuenta, IP, reloj | Alto | Contraseña corregida; MFA y LogonId |
| AUTH-03 | Security 4624 desde IP global; excluye rangos de documentación | Medio | VPN/NAT autorizado; política y origen real |
| PRIV-01 | Security 4672, host/cuenta en episodios de 30 min | Medio | Administrador legítimo; no demuestra escalamiento |
| PRIV-02 | Security 4728/4732/4756/4704 | Alto | Cambio de grupo/permiso aprobado; verificar grupo, actor y miembro |
| PROC-01 | 4688/Security, 1/Sysmon o 4104/PowerShell con parámetro PowerShell codificado | Alto | Automatización; recuperar contenido y proceso padre |
| PROC-02 | Esos proveedores/eventos con eliminación de sombras/catálogo de backups | Crítico | Mantenimiento; verificar efecto y autorización |
| PROC-03 | Sintaxis procdump+lsass, comsvcs+minidump o sekurlsa | Crítico | Diagnóstico; comprobar destino de memoria y artefactos |
| PROC-04 | Sintaxis tar/7z/Compress-Archive | Medio | Backup; verificar archivo y contenido |
| PROC-05 | Comandos de descarga con URL | Medio | Instalador; firma, contenido y cambio |
| DISC-01 | net view, Get-LocalGroupMember, Get-SmbShare | Bajo | Inventario; finalidad de la sesión |
| LAT-01 | PsExec, WMIC /node, WinRS -r, schtasks /s | Alto | Administración; destino y autorización |
| LAT-02 | Security 4624, LogonType=3 y source=host explícitos | Medio | Acceso legítimo; no declara movimiento malicioso |
| LAT-03 | Security 4624 en ≥3 hosts/15 min, misma cuenta/IP | Medio | NAT, servicio o administrador; LogonId y dispositivo |
| PERSIST-01 | Security 4698 o System 7045 | Medio; Alto si ProgramData/Temp/PowerShell | Instalación aprobada; firma y ticket |
| AUDIT-01 | Security 1102 o System 104 | Alto | Mantenimiento; actor y copia central |
| WEB-01 | IIS HTTP_ACCESS con parámetro cmd/exec/command; mismo host/IP, 15 min | Alto | Parámetro legítimo; contenido del sitio y request ID |
| WEB-02 | Proceso cmd/PowerShell bajo cuenta IIS APPPOOL | Alto | Función de aplicación; proceso padre y request ID |
| DATA-01 | Security 4663 ≥10/5 min, mismo host/cuenta/IP/destino | Medio | Backup/indexación; AccessMask y objetos |
| DATA-02 | Proxy bytes_out ≥50 000 000 en episodio de 10 min, host/cuenta/IP/destino comunes | Alto | Carga autorizada; DLP y contenido |
| ML-01 | Isolation Forest, score >0.65; máximo 10 eventos; ≥30 filas únicas | Bajo | Rareza legítima; baseline y casos etiquetados |

Eventos con campos temporales no interpretables se conservan, pero no entran en
agrupaciones temporales. Los campos de origen ausentes impiden correlaciones;
no se rellenan. Las reglas de sintaxis no decodifican ni ejecutan comandos.

## Criticidad, confianza y decisiones

- **Crítico:** sintaxis que podría afectar recuperación o credenciales. El
  resultado real del comando no está demostrado.
- **Alto:** patrones con capacidad de acceso no autorizado, persistencia,
  ejecución o transferencia que justifican revisión prioritaria.
- **Medio:** acciones administrativas, acceso o preparación de datos cuyo
  carácter anómalo depende de contexto.
- **Bajo:** enumeración o anomalías estadísticas sin impacto sustentado.

Estas categorías estiman impacto potencial y no probabilidad. La confianza se
declara por hallazgo; una alta confianza en un patrón puede coexistir con baja
confianza en compromiso. No hay puntuaciones CVSS ni atribución de actores.

Las asociaciones requieren **host + cuenta + IP + mismo dominio temporal**,
con dos evidencias a ≤30 minutos y categorías distintas. Se excluyen ML-01,
PRIV-01 y LAT-03 de esa asociación para limitar ruido. Se conservan pares
contextuales y no se forman cadenas transitivas. «10 asociaciones» no equivale
a «10 incidentes». No se vinculan hosts por similitud de nombre, PID aislado o
proximidad temporal.

No hay inventario validado, horarios autorizados, geolocalización ni baseline.
Por ello no se afirman «viaje imposible», «horario no autorizado», «IP maliciosa»
o «exfiltración confirmada». La dimensión horaria del modelo sólo refleja rareza
relativa en la muestra.

## Validación y evolución

La suite pública usa datos sintéticos pequeños y prueba casos positivos,
negativos y datos faltantes. Las métricas de precisión/recall no se publican:
se necesita un conjunto representativo etiquetado y validado por un analista.
Para incorporar otro proveedor, añade un mapping explícito, una semántica
documentada y pruebas negativas. No basta con coincidir en el Event_ID.
