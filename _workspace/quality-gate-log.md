## 2026-06-03T16:42:21 | phase=all | status=BLOCKED

- strict: True
- problem_data: _workspace\input\problem_data.json
- model: _workspace\phase-1-model.xml
- run: _workspace\run-20260601-103030

- WARN: [model] recommended modeling section/marker not found: feasibility_precheck
- WARN: [model] recommended modeling section/marker not found: baseline_and_invariants
- WARN: [model] recommended modeling section/marker not found: implementation_contract
- WARN: [model] model text still contains placeholder or self-assumption wording
- WARN: [model] 12/36 critical numeric values from problem_data are not explicit in model text; first: missiles.M2[0]=19000, missiles.M2[2]=2100, missiles.M3[1]=-600, missiles.M3[2]=1900, uavs.FY2[0]=12000, uavs.FY2[1]=1400, uavs.FY2[2]=1400, uavs.FY3[1]=-3000, uavs.FY3[2]=700, uavs.FY4[0]=11000, uavs.FY5[1]=-2000, uavs.FY5[2]=1300
- WARN: [code] solver contains TODO/pass markers; confirm they are intentional
- WARN: [run] Q5 duration is zero; require explicit feasibility diagnostic and paper explanation
## 2026-06-03T16:42:22 | phase=all | status=PASS

- strict: False
- problem_data: _workspace\input\problem_data.json
- model: _workspace\phase-1-model.xml
- run: _workspace\run-20260601-103030

- WARN: [model] recommended modeling section/marker not found: feasibility_precheck
- WARN: [model] recommended modeling section/marker not found: baseline_and_invariants
- WARN: [model] recommended modeling section/marker not found: implementation_contract
- WARN: [model] model text still contains placeholder or self-assumption wording
- WARN: [model] 12/36 critical numeric values from problem_data are not explicit in model text; first: missiles.M2[0]=19000, missiles.M2[2]=2100, missiles.M3[1]=-600, missiles.M3[2]=1900, uavs.FY2[0]=12000, uavs.FY2[1]=1400, uavs.FY2[2]=1400, uavs.FY3[1]=-3000, uavs.FY3[2]=700, uavs.FY4[0]=11000, uavs.FY5[1]=-2000, uavs.FY5[2]=1300
- WARN: [code] solver contains TODO/pass markers; confirm they are intentional
- WARN: [run] Q5 duration is zero; require explicit feasibility diagnostic and paper explanation
## 2026-06-17T13:55:01 | phase=modeling | status=PASS

- strict: False
- problem_data: _workspace\run-20260617-133444\input\problem_data.json
- model: _workspace\phase-1-model.xml

- WARN: [model] recommended modeling section/marker not found: feasibility_precheck
- WARN: [model] recommended modeling section/marker not found: baseline_and_invariants
- WARN: [model] recommended modeling section/marker not found: implementation_contract
- WARN: [model] model text still contains placeholder or self-assumption wording
- WARN: [model] 12/34 critical numeric values from problem_data are not explicit in model text; first: initial_positions.missiles.M2[0]=19000, initial_positions.missiles.M2[2]=2100, initial_positions.missiles.M3[1]=-600, initial_positions.missiles.M3[2]=1900, initial_positions.drones.FY2[0]=12000, initial_positions.drones.FY2[1]=1400, initial_positions.drones.FY2[2]=1400, initial_positions.drones.FY3[1]=-3000, initial_positions.drones.FY3[2]=700, initial_positions.drones.FY4[0]=11000, initial_positions.drones.FY5[1]=-2000, initial_positions.drones.FY5[2]=1300
## 2026-06-17T13:55:03 | phase=coding | status=PASS

- strict: False
- problem_data: _workspace\run-20260617-133444\input\problem_data.json
- run: _workspace\run-20260617-133444

- WARN: [run] unreferenced figures in run directory: ['fig03-Q2-cloud-vs-missile-xz.png', 'fig05-missile-drone-overview.png']
- WARN: [run] figure names do not match figNN_*.png: ['fig05-missile-drone-overview.png', 'fig01-Q1-occlusion-timeline.png', 'fig03-Q2-cloud-vs-missile-xz.png', 'fig02-Q2-convergence.png', 'fig04-Q1-Q5-duration-comparison.png']
