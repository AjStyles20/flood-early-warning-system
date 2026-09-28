# Chapter Five Draft — Conclusion, Limitations and Future Work

## 5.1 Summary

FloodWatch was developed as a flood monitoring and decision-support prototype and then narrowed into an evidence-driven research testbed.

The project originally considered a broad combination of IoT sensing, machine learning, dashboards and alerts. Literature and prior-art review showed that such a combination is already common and should not be claimed as the novelty.

The final research direction therefore focused on a more defensible question: whether additional predictive complexity produces a useful early-warning advantage over a strong interpretable baseline when both methods are evaluated on real Lokoja river observations.

## 5.2 Engineering Conclusion

The implemented system demonstrates the core end-to-end software architecture:

physical/controlled source or simulator -> telemetry ingestion -> validation/provenance -> persistent storage -> current-state assessment -> dashboard/data display -> alert workflow.

The existing physical prototype has demonstrated Pico-to-serial-bridge-to-FastAPI integration. The software repository further contains normalized observation infrastructure, MySQL-capable persistence, automated regression testing, operator workflows and accessible dashboard interfaces.

The engineering prototype should not be described as a calibrated operational Lokoja gauge or a national flood-warning service.

## 5.3 Research Conclusion

Experiment 001 compared the B3 interpretable trend rule with a lightweight Random Forest using real GRDC mean daily discharge observations for the River Niger at Lokoja.

The experiment used a chronological training, validation and final holdout design and evaluated multiple warning horizons.

The evidence does not support a general statement that Random Forest materially outperforms B3.

At shorter horizons the simple rule is equal or stronger on important metrics. At longer horizons Random Forest can improve recall and warning lead time, but the improvement is accompanied by a higher false-alarm burden.

The defensible conclusion is therefore:

> A strong interpretable trend-based method captures a substantial amount of the useful warning information available in local Lokoja discharge history. Lightweight machine learning can change the recall/lead-time trade-off at longer horizons, but the present evidence does not establish a robust material advantage sufficient to replace the simpler operational logic.

## 5.4 Contribution

The contribution is not a new Random Forest algorithm and not the claim that FloodWatch is the first AI/IoT flood-warning system.

The contribution is the combination of:

1. a working source-aware flood monitoring and decision-support prototype;
2. an explicit separation between current-state operational logic and predictive research;
3. an honest real-data comparison between an interpretable warning rule and lightweight machine learning;
4. a result showing when additional complexity does and does not appear useful under the tested Lokoja conditions;
5. a traceable architecture in which future sensing/data additions must be hydrologically justified rather than added for novelty.

## 5.5 Limitations

The principal limitations are:

- the primary experimental target is a statistically defined high-flow threshold, not an official NIHSA discharge alert threshold;
- no permanent stage-discharge conversion is assumed;
- the final holdout contains only a small number of independent usable high-flow crossing events;
- the experiment uses daily discharge, so it does not evaluate minute-scale or flash-flood warning;
- upstream Niger/Benue state, catchment rainfall and soil-wetness information are not yet included in RQ1;
- the physical prototype has not been field-calibrated at Lokoja;
- the Pico/potentiometer demonstration is a controlled analogue integration test, not a real Lokoja water-level measurement;
- the post-migration physical Pico/MySQL regression and final local screenshots require the user's actual hardware and computer environment;
- the prototype alert channels are advisory/simulated unless a real provider is separately configured and tested.

## 5.6 Recommendations

For the current defense version:

- retain the interpretable threshold/current-state engine as the operational default;
- present Experiment 001 as a separate real-data research result;
- do not state that machine learning won;
- do not describe the Q95 boundary as an official flood threshold;
- clearly distinguish simulated, hardware, observed and modelled evidence;
- complete the final local Pico/MySQL regression and capture screenshots before defense.

## 5.7 Future Work

The strongest next research extension is not to add arbitrary sensors. It is to test whether hydrologically justified external information contributes incremental warning value.

Priority candidates are:

- upstream River Niger conditions;
- upstream River Benue conditions;
- basin/catchment rainfall;
- potentially soil-wetness information where a defensible spatial dataset is available.

A future experiment should ask whether those variables improve event detection or useful lead time beyond local discharge history and whether any gain justifies the extra data, sensing and operational complexity.

Other future engineering work includes physical water-level sensor calibration, controlled or accessible-site validation, authoritative threshold integration where obtainable, and production-grade emergency-message provider integration.

## 5.8 Final Statement

FloodWatch should be defended as an evidence-driven engineering and research project rather than as an “AI automatically predicts floods” product.

Its strongest position is that the system works as a prototype, the historical experiment uses real observations, the negative/mixed ML result is reported rather than hidden, and the final design follows what the evidence supports.
