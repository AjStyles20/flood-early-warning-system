# Chapter Two Working Literature Review - Evidence-Controlled Draft

Status: working draft. This document separates **source-supported findings** from **project interpretation**. It must not be treated as a final bibliography until the original publications are verified and cited directly.

## 2.1 Literature-review purpose

The review is used to establish what a flood early warning system (FEWS) is expected to do, identify recurring limitations in existing systems, determine which technological approaches are already occupied prior art, and derive only those FloodWatch requirements that are justified by the evidence.

The project does not treat the mere combination of IoT, artificial intelligence, GIS/dashboard functions and alerts as novelty. These technologies are already represented in the reviewed FEWS literature.

## 2.2 FEWS as a socio-technical system

The reviewed material consistently describes effective early warning as more than prediction. Four recurring functions are:

1. risk knowledge;
2. monitoring and forecasting/warning services;
3. dissemination and communication; and
4. preparedness/response capability.

This framing means that a technically accurate model alone is not a complete FEWS. FloodWatch therefore distinguishes observation, prediction/research, interpretation, communication and human decision-support responsibilities.

## 2.3 Monitoring and data limitations

The reviewed material reports recurring deficiencies in hydrological gauge coverage, measurement/transmission equipment, manual data transfer and centralized data management. It also identifies satellite precipitation, remote sensing, soil-moisture products and IoT sensing as mechanisms for supplementing conventional monitoring.

### Project interpretation

For FloodWatch, this supports a provenance-aware multi-source data architecture rather than a fixed assumption that every record contains the same variables. Physical stage-like measurements, authoritative discharge observations, external rainfall evidence, derived variables and simulations must remain distinguishable.

It does **not** justify claiming that every possible source must be implemented in the FYP.

## 2.4 AI, IoT and remote sensing as established prior art

The reviewed material discusses AI/deep learning, data-driven models, IoT sensors, satellite rainfall, remote sensing, hydrological/hydraulic models, cloud platforms and related technologies as existing FEWS directions.

### Novelty implication

Accordingly, the following broad claim is rejected:

> FloodWatch is novel because it combines AI and IoT for flood early warning.

The defensible research contribution must instead be evaluated at the level of a specific mechanism, comparison or empirical finding.

## 2.5 Model reliability, evaluation and complexity

The reviewed material identifies model accuracy/reliability, uncertainty and limited formal technical evaluation as continuing concerns. It also points toward benchmarking and approaches that can operate without unnecessarily heavy computing infrastructure.

### FloodWatch research connection

This supports the current controlled empirical question: whether a lightweight data-driven predictor provides a materially useful warning advantage over a calibrated, interpretable trend-based warning rule at equivalent warning horizons using independent observational evidence.

The project must therefore report comparative predictive performance rather than assuming that machine learning is superior because it is more complex.

## 2.6 Last-mile communication and human response

The reviewed material repeatedly identifies communication failure as a major FEWS weakness. Problems include technical warning terminology, lack of localization, connectivity limitations, trust and difficulty converting forecasts into actions that communities can understand.

### FloodWatch requirement implication

Decision-support output should therefore preserve the underlying technical state while presenting:

- explicit textual risk levels;
- plain-language advisory explanations;
- accessible alternatives to colour/map-only information;
- source/provenance and freshness context;
- localization/language capability where implemented; and
- clear deference to official emergency guidance.

These features are communication/accessibility requirements, not evidence that FloodWatch has measured community behaviour or evacuation effectiveness.

## 2.7 Low-resource and resilience context

The reviewed material identifies insufficient monitoring infrastructure, maintenance limitations, funding constraints, communication outages and technical-capacity shortages as barriers, particularly in lower-resource settings. Low-cost sensing, edge processing and resilient communication are proposed directions in the reviewed material.

### Scope boundary

FloodWatch may evaluate lightweight/local processing and low-cost prototype integration where these support the research and engineering objectives. Blockchain, 5G, drones, social-media mining, physics-informed neural networks and other technologies mentioned in the literature are **not automatically project requirements**.

## 2.8 Evidence-to-requirement synthesis

**Figure 2.x — Evidence-to-decision-support architecture derived from the literature synthesis**

![FloodWatch evidence-to-decision-support architecture](diagrams/floodwatch_evidence_to_decision_support.svg)

The figure is a FloodWatch design synthesis, not a diagram reproduced from any reviewed publication. It shows how the literature findings are translated into project boundaries while preserving the separate research promotion gate.

| Literature finding | FloodWatch implication | Requirement/design area |
|---|---|---|
| FEWS has monitoring, communication and response dimensions | Do not reduce architecture to sensor -> ML | layered architecture |
| Gauge/data limitations are recurrent | support heterogeneous evidence and provenance | FR-02, FR-03, FR-13; normalized observation model |
| AI/IoT already established | reject broad technology-combination novelty | research framing |
| Model reliability/evaluation remains important | compare lightweight ML against interpretable baseline | RQ1 / research plane |
| Technical warnings can fail at the last mile | plain-language, textual and accessible status | FR-07, FR-08, NFR-05 |
| Communication infrastructure can fail | keep channel capability explicit; do not claim untested delivery | alert/notification design |
| Human response matters | system remains decision support and defers official authority | NFR-10 |

## 2.9 Gap-to-contribution structure

FloodWatch does not claim that every weakness of a complete FEWS is solved by this FYP. The literature findings are classified by what the project can actually investigate or implement.

| Gap/problem class | FloodWatch response | Evidence/claim level |
|---|---|---|
| Model reliability and limited comparative evaluation | Compare an interpretable trend baseline with lightweight ML at equivalent warning horizons | **Primary scientific research contribution** |
| Fragmented/heterogeneous monitoring evidence | Provenance-aware Station/Variable/DataSource/Dataset/Observation architecture | **Data/software engineering contribution** |
| Low-cost monitoring constraints | Pico-to-API physical prototype and modular source adapters | **Prototype engineering contribution** |
| Technical/last-mile warning presentation | Plain-language textual state, accessible dashboard and localization capability | **Decision-support design contribution** |
| Community trust, comprehension and behavioural response | Not evaluated without a human/community study | **Not claimed as solved** |
| Evacuation logistics, shelters and institutional coordination | Outside the software prototype's authority/scope | **Out of scope** |

This classification prevents a system feature from being misrepresented as a scientifically evaluated research result.

## 2.10 Research gap used by FloodWatch

The literature reviewed so far does not justify claiming a globally new FEWS architecture or a new AI algorithm. The working gap is narrower: rigorous, context-bounded evidence is needed on whether additional predictive complexity produces a practically meaningful early-warning advantage over simpler interpretable warning logic under the evaluated observational conditions, while the engineering prototype demonstrates how provenance-aware observations can be carried through monitoring and decision support.

This statement remains subject to direct verification against the original publications and the broader prior-art search.

## 2.11 Source-verification gate

The current notes summarize three sources:

1. *Challenges and Technical Advances in Flood Early Warning Systems (FEWSs)* — Perera, Seidou, Agnihotri, Mehmood and Rasmy.
2. *Early warning systems in climate risk management: Roles and implementations in eradicating barriers and overcoming challenges* — reported in the notes as a 2025 Natural Hazards Research article.
3. UNU-INWEH Report Series Issue 08, *Flood Early Warning Systems: A Review of Benefits, Challenges and Prospects* (2019).

Before final Chapter Two submission, each original publication must be retrieved and checked for authorship, year, bibliographic metadata, exact findings and whether statements labelled in the notes as “Potential Contribution” or “Your Contribution” are the original authors' claims or later interpretation. The final thesis should cite the original sources, not these working notes as substitutes.
