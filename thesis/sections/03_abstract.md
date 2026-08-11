<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/main.tex (Resumo + Abstract)
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Resumo

\[Provisional — rewritten after data freeze\] Os gémeos digitais de dispositivos de consumo dependem, com frequência, de plataformas cloud centralizadas, o que levanta questões de latência, de disponibilidade e de controlo dos dados por parte do consumidor. Esta dissertação concebe e implementa um *edge gateway* ARM64 reproduzível, construído com o Yocto Project (linha LTS Scarthgap) e composto por serviços contentorizados — broker MQTT com TLS, controlador de ingestão e Eclipse Ditto com MongoDB — concebido para receber telemetria sintética concorrente de três tipos de wearables (smartwatch, smart ring e smart clothing), validar os eventos contra esquemas JSON versionados e materializá-los como gémeos digitais. A avaliação segue um protocolo experimental pré-especificado, congelado antes da recolha de dados e a executar num ambiente ARM64 nativo, medindo latência, débito, consumo de recursos e estabilidade. Todos os resultados quantitativos serão introduzidos apenas após o *data freeze*, a partir de dados brutos com manifesto e análise reproduzível.

<span class="smallcaps">Palavras Chave:</span> *edge computing*, *gémeos digitais*, *Yocto Project*, *ARM64*, *MQTT*, *wearables*

# Abstract

\[Provisional — rewritten after data freeze\] Digital twins of consumer devices frequently depend on centralised cloud platforms, raising latency, availability and data-control concerns. This dissertation designs and implements a reproducible ARM64 edge gateway, built with the Yocto Project (Scarthgap LTS line) and composed of containerised services — an MQTT broker with TLS, an ingestion controller, and Eclipse Ditto backed by MongoDB — designed to receive concurrent synthetic telemetry from three wearable-device types (smartwatch, smart ring and smart clothing), validate events against versioned JSON Schemas, and materialise them as digital twins. The evaluation follows a pre-specified experimental protocol, frozen before data collection and to be executed on a native ARM64 environment, measuring latency, throughput, resource consumption and stability. All quantitative results are introduced only after the data freeze, from raw data with manifests and a reproducible analysis pipeline.

<span class="smallcaps">Keywords:</span> *edge computing*, *digital twins*, *Yocto Project*, *ARM64*, *MQTT*, *wearable devices*
