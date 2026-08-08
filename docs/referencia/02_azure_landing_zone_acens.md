<!-- docs/referencia/02_azure_landing_zone_acens.md -->
# Landing Zone de Azure — documento de diseño de acens

> Origen: `CO388632 Construcciones Ruesma - Documento Entregable.pdf`, acens ·
> Fecha del documento: 2026-03-25
> Convertido a Markdown el 2026-08-08 con la herramienta MCP `markitdown`.
> El PDF original vive fuera del repositorio.

> **Confidencialidad.** El original lleva una declaración de confidencialidad:
> es propiedad de acens y prohíbe su reproducción total o parcial sin permiso
> escrito. Esta versión existe solo como referencia interna del proyecto; no
> se difunde fuera de él.

> **Redactado.** Se han sustituido por marcadores los rangos de red
> (`<RANGO-*>`, `<SUBRED-*>`, `<RED-SEDE-CLIENTE>`) y los dos correos
> destinatarios de alertas (`<correo-alertas-1>`, `<correo-alertas-2>`). El
> detalle real está en el PDF original. Todo lo demás es fiel al documento.

## Por qué está aquí

Describe los cimientos de Azure sobre los que se despliega este ETL. Es el
contexto de las features F-005 (Postgres en Azure), F-003 (Container Apps Job)
y F-006 (MCP contra Azure), y aporta base para cerrar las decisiones D1
(acceso de red al Postgres) y D3 (¿solo dev o también producción?) de
`progress/decisiones_abiertas.md`.

---

## 1. Introducción

Solución propuesta de instalación de **Landing Zone Fundacional** para que
Construcciones Ruesma pueda migrar su carga de trabajo local a Azure.

### 1.1 Objetivo

Desplegar una Landing Zone siguiendo las buenas prácticas de Microsoft, con
estos requisitos:

- Énfasis prioritario en la **velocidad de implementación**.
- Despliegue de la aplicación en **una sola región**.
- **No** requiere soluciones de DR (recuperación ante desastres).
- De momento **no** hay requisito de alta disponibilidad.
- **MFA** obligatorio para iniciar sesión en la consola.
- Estrategia estándar de tags, inventariado y monitorización.
- Pack de alertas de coste por defecto.
- Guardrails obligatorios y altamente recomendados, por defecto.

### 1.2 Alcance del servicio

Despliegue de plantillas **Terraform** para crear los cimientos de
construcción de servicios sobre Azure. Características incluidas:

- Estructura de arrendamiento en la nube (cuentas, seguridad, servicios
  compartidos, escalabilidad futura).
- Conectividad entre la nube y la red de cliente mediante **VPN**.
- Seguridad, cumplimiento y gobernanza.
- Gestión de identidades y accesos.
- Cortafuegos virtuales.
- Agregación de registros.
- Políticas de remediación.
- Monitorización y administración con características nativas.

## 2. Cloud Tenancy y estructura de cuentas

### 2.1 Selección de región

| # | Parámetro de selección | Respuesta |
|---|---|---|
| 1 | Ubicación de los clientes que accederían a los servicios | Limitado al entorno de Europa |
| 2 | Requisitos de cumplimiento normativo | GDPR |
| 3 | ¿Aplicaciones que necesiten baja latencia? ¿Dónde? | Solo dentro de España |
| 4 | Servicios clave de Azure requeridos | Principalmente BBDD y almacenamiento |
| 5 | ¿Requisito de recuperación ante desastres? | No |

| Decisión de diseño | Motivo |
|---|---|
| El despliegue principal se realizará en **Spain Central (Madrid)** | Menor latencia entre la sede de cliente y Azure |

### 2.2 Estructura de cuentas y jerarquías

| # | Consideración | Respuesta |
|---|---|---|
| 1 | ¿Aislamiento de facturación entre unidades de negocio o cargas de trabajo? | Sin necesidades específicas |
| 2 | ¿Aislamiento administrativo por requisitos normativos o políticas distintas? | No hay necesidad de dividir costes por entornos productivos/no productivos, aunque **se plantea división por entorno DEV/STA/PRO** |
| 3 | ¿Limitación de servicios según tipo de suscripción? | Sin necesidades específicas |
| 4 | Nº estimado de instancias reservadas e IPs públicas dinámicas | Menos de 50 VMs y 10 IPs públicas |
| 5 | ¿Suscripción de seguridad separada? | No |

Jerarquía propuesta:

```
ORG
└── Platform
    ├── SPOKE1
    ├── HUB
    └── SPOKE2
```

## 3. Diseño de seguridad y cumplimiento

### 3.1 Matriz de responsabilidad compartida

`M` = Microsoft · `C` = Cliente · `S` = compartida entre cliente y Azure.

| Responsabilidad | SaaS | PaaS | IaaS | On-Prem | Servicios en Azure |
|---|---|---|---|---|---|
| Account | C | C | C | C | Azure Enrolment, Account, Department, Management Groups, Subscription, Resource Group |
| Identity and directory infrastructure | S | S | C | C | RBAC, Active Directory |
| Application | M | S | C | C | — |
| Network controls | M | S | C | C | VNet, Subnet, NSG, Peering, S2S, ExpressRoute |
| Operating system | M | M | C | C | Ubuntu, CentOS, Windows, etc. |
| Physical hosts | M | M | M | C | — |
| Physical network | M | M | M | C | — |
| Physical datacentre | M | M | M | C | — |
| Data classification | C | C | C | C | — |
| Data security | C | C | C | C | — |

### 3.2 Microsoft Entra ID

Servicio de directorio distribuido multiinquilino y multiaplicación. Se
habilitará **MFA**. Estas configuraciones las realiza **en su totalidad el
cliente**: quedan excluidas del alcance de esta provisión.

### 3.3 Azure Firewall

Servicio stateful con alta disponibilidad integrada y escalabilidad. Se usa en
**modalidad Basic** para filtrar el tráfico entre Azure y la infraestructura
local, y para gestionar el tráfico de Internet siguiendo los patrones
*North-South* y *East-West*. Las reglas se definen según los requisitos de
cada aplicación.

| Característica | Descripción |
|---|---|
| High Availability | HA integrada; no hace falta desplegar varias instancias como con NVAs |
| Cloud Scalability | Escala para satisfacer requisitos de rendimiento y ancho de banda |
| FQDN filtering | Lista blanca de FQDN (admite comodines) accesibles desde la red; limita la fuga de datos y el control remoto por malware |
| Network filtering rules | Reglas por origen, destino, protocolo y puerto sobre el tráfico saliente de la VNet |
| Outbound SNAT Support | IP pública estándar; todo el tráfico saliente se identifica en Internet por esa dirección |
| Monitoring Support | Eventos rastreables en Azure Monitor y archivables en storage account, event hub o Log Analytics |

### 3.4 Azure Backup

Construcciones Ruesma pide **copias de seguridad inmutables** de sus bases de
datos. Tres políticas:

| Política | Ámbito | Frecuencia | Retención |
|---|---|---|---|
| `GOLDEN-vm` | Máquinas virtuales | Diaria | 14 días |
| `SILVER-vm` | Máquinas virtuales | Semanal | 8 semanas |
| `GOLDEN-sql` | SQL | Diaria, con copiado de log cada 2 horas | 14 días |

| Decisión de diseño | Motivo |
|---|---|
| Copias de seguridad gestionadas por política de Azure | Facilidad de gestión |
| Se establecerán tags según la frecuencia de copiado necesaria | Mayor granularidad en la definición de RPO |

### 3.5 Azure Policy

Políticas que se implementarán, entre otras:

| Nombre | Descripción |
|---|---|
| `Deny-UnmanagedDisk` | Deny virtual machines and virtual machine scale sets that do not use managed disk |
| `Audit-ResourceRGLocation` | Resource Group and Resource locations should match |
| `Deny-Classic-Resources` | Deny the deployment of classic resources |
| `Audit-TrustedLaunch` | Audit virtual machines for Trusted Launch support |
| `Deploy-Diag-LogsCat` | Enable category group resource logging for supported resources to Log Analytics |
| `Audit-UnusedResources` | Unused resources driving cost should be avoided |
| `Deploy-ASC-Monitoring` | Microsoft Cloud Security Benchmark |
| `Enforce-ACSB` | Enforce Azure Compute Security Baseline compliance auditing |
| `Deploy-AzActivity-Log` | Configure Azure Activity logs to stream to specified Log Analytics workspace |
| `acens-owner-limit` | Impedir asignación de rol owner |
| `acens-locations` | Ubicaciones permitidas para despliegue por acens |
| `Enforce-Subnet-Private` | Subnets should be private |
| `Enforce-ASR` | Enforce enhanced recovery and backup policies |
| `Deploy-VM-ChangeTrack` | Enable Change Tracking and Inventory for virtual machines |
| `Enforce-GR-KeyVault` | Enforce recommended guardrails for Azure Key Vault |
| `Deploy-VM-Monitoring` | Enable Azure Monitor for VMs |

### 3.6 Tags

Para agrupar recursos por proyecto y/o departamento y poder asociar centros de
coste, se crean estos tags con una política que los aplica a todos:

`acens-support`, `acens-backuppolicy`, `acens-shutdownpolicy`,
`acens-patchpolicy`, `acens-customer`, `acens-environment`, `acens-project`,
`acens-costcenter`, `acens-sla`, `acens-compliance`,
`acens-retentionpolicy`, `acens-terraform`, `acens-responsable-iac`,
`acens-responsable-so-app`.

### 3.7 Detección de malware

Construcciones Ruesma dispone de sus propias herramientas de protección de
cargas de trabajo, por lo que **no** se despliega una solución dentro del
alcance.

## 4. Red

### 4.1 Diseño de redes

Arquitectura **hub & spoke** para centralizar las comunicaciones, con un
firewall centralizado que filtra el tráfico.

| Dirección de red | Observaciones |
|---|---|
| `<RANGO-CUENTA>` | Rango planificado para toda la cuenta de Azure |
| `<RANGO-MANAGEMENT>` | Rango planificado para Management |
| `<RANGO-HUB>` | Rango reservado para los servicios de HUB |
| `<RANGO-PRO>` | Rango planificado para entorno PRO |
| `<RANGO-DEV-POC>` | Rango planificado para entorno DEV/POC |

### 4.2 Diseño de subredes

Subredes dentro de la red de HUB (`VNET-HUB-SPAINCENTRAL`, `<RANGO-VNET-HUB>`):

| Subred | Observaciones |
|---|---|
| `<SUBRED-FIREWALL>` | Firewall |
| `<SUBRED-FIREWALL-MGMT>` | Firewall Management |
| `<SUBRED-BASTION>` | Bastión |
| `<SUBRED-GATEWAYS>` | Gateways |

### 4.3 Red híbrida

Para las comunicaciones con el entorno *on-premise* caben conexiones
Site-to-Site (VPN), Point-to-Site (VPN SSL) y Azure ExpressRoute (ER). Según
los requerimientos, **se hace uso de VPN SSL**.

Se configurará además una **conexión VPN Site-to-Site** para enlazar de forma
permanente y cifrada la red local del cliente con la infraestructura remota,
mediante túneles IPsec. Habilita integración híbrida directa: ambos entornos
operan como una única red privada.

| Tipo | Red remota | Descripción |
|---|---|---|
| VPN `VpnGw1` | `<RED-SEDE-CLIENTE>` | Red de sede de cliente |

### 4.4 Comunicación entre VNets y tablas de rutas

La comunicación entre la VNet del HUB y las VNets *spoke* se realiza mediante
**peering**, con la configuración de Firewall definiendo la seguridad de las
conexiones cuando sea necesario. En fase de verificación se determinó que no
hacían falta tablas de rutas adicionales.

### 4.5 Network Security Group

Los NSG son firewalls virtuales que bloquean tráfico entrante o saliente, a
nivel de subred o de NIC. **Debido al despliegue de Azure Firewall, no se
provisionan NSGs en esta etapa del proyecto.**

## 5. Monitorización

Tres tipos: de **plataforma** (cuenta, red, seguridad y costes), de
**infraestructura** (VMs, bases de datos) y de **aplicaciones**.

### 5.1.1 Monitorización de seguridad

**Defender for Cloud** para gestión de la seguridad y protección contra
amenazas.

| Parámetro | Respuesta |
|---|---|
| ¿Cómo se monitoriza la seguridad y el cumplimiento del entorno actual? | No existe monitorización específica |
| Requisitos de registro y auditoría desde seguridad | Centralización de logs y **retención de 30 días** para auditoría |

| Decisión de diseño | Racional |
|---|---|
| Se utilizará el plan **Foundational CSPM** como solución de auditoría | Provee protección ante amenazas mediante registro centralizado de logs y auditoría |

Notificaciones de seguridad a: `<correo-alertas-1>`, `<correo-alertas-2>`.

### 5.1.2 Monitorización de costes

**Cost Management** para explorar y analizar los costes; *budgets* y *budget
alerts* para detectar irregularidades en el gasto.

| Decisión de diseño | Racional |
|---|---|
| Un **Budget por suscripción** con su alerta, notificando a `<correo-alertas-1>` y `<correo-alertas-2>` | Analizar los costes de la infraestructura y recibir alerta cuando se supere |

### 5.2 Monitorización de infraestructura

- **Azure Monitor**: recopila datos de aplicación, SO y recursos de Azure;
  los almacena como métricas y registros; y sobre ellos hace análisis,
  alertas y transmisión a sistemas externos.
- **Log Analytics y Log Queries**: se desplegará un *Log Analytics workspace*
  para recolectar y centralizar registros, permitiendo supervisar estado y
  utilización de los recursos únicamente con servicios nativos de la nube.

## 6. CI/CD con Azure DevOps

El despliegue se realiza con **IaC en Terraform**, desplegada mediante
**pipelines de Azure DevOps** en formato CI/CD.

El flujo se basa en repositorios Git alojados en Azure DevOps. Todo cambio en
las plantillas de infraestructura desencadena pipelines que ejecutan
validaciones sintácticas, análisis estático de seguridad, pruebas de
compilación y generación de artefactos listos para despliegue.

Los pipelines de release aplican controles formales: revisión obligatoria,
bloqueo por políticas, dependencias explícitas entre entornos y uso de
**identidades gestionadas** para desplegar en Azure con privilegios mínimos.
El despliegue es **idempotente**.

Resultado:

- Infraestructura gobernada por código, sin intervenciones manuales.
- Trazabilidad absoluta de cada cambio.
- Ciclos repetibles para desarrollo, integración, preproducción y producción.
- Cumplimiento automático del modelo del Landing Zone Accelerator.
- Reducción del riesgo operativo mediante validación temprana y despliegue
  automatizado.

La plataforma actúa como **única vía oficial** para la provisión,
actualización y mantenimiento de la Landing Zone.
