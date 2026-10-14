# REA 函数证据索引

本目录提供 38 个已保存函数的审阅摘出副本。[function-observations.json](function-observations.json) 保留原始返回文件的 SHA-256、REA Evidence ID、目标指纹、完整汇编、函数边界与调用者／被调用者地址。这些摘出副本不替代 REA canonical Evidence，不能以摘出 JSON 的字节重新计算原始 Evidence ID。原始结构化返回值、16.6 MB 证据包和 33.1 MB 会话快照留存在分析机器，没有随本 PR 上传。

组织函数、CSimData 构造函数及工作函数的原始 `native_value_flow` 子字段截断；完整的汇编和已保存伪代码仍可检查。函数内数据流不能充当完整跨函数证明。

| 静态地址 | 伪代码 | 原始 Evidence ID |
| --- | --- | --- |
| `0x140d8e6c0` | [function-boxmuller.c](../../decompiled/function-boxmuller.c) | `ev_436ab885cb65157bd69a90db84bb4f5af48cac007a1119a058bc7b595d1f7e16` |
| `0x140d8e9d0` | [function-calendar-start.c](../../decompiled/function-calendar-start.c) | `ev_d8ab95336e5a82c1d56c9c0e912a48240421e80b7038f22ca8886db1916f1c33` |
| `0x140e5eff0` | [function-error-vector.c](../../decompiled/function-error-vector.c) | `ev_df61d03c396448c2fe5923ada5a7b5ba92a297a498c6435e2d52c5ad5b0cdbbc` |
| `0x140d8e8f0` | [function-event-loop.c](../../decompiled/function-event-loop.c) | `ev_1165eef43fbca2663726b7825f9f5c507df71525a5dd3b00a7ac5bdc06997053` |
| `0x140d8ea60` | [function-event-order.c](../../decompiled/function-event-order.c) | `ev_1edeecc93bd83acf9cf89d8eb96d206a283fcdecde1f65b3c0b54e3f6a08b3da` |
| `0x140c4a8f0` | [function-exp-kernel.c](../../decompiled/function-exp-kernel.c) | `ev_779ea422ae248d03ba7907d5a65a250d052a1efb86aa79540144e32c760adec2` |
| `0x140d8e640` | [function-exp-math.c](../../decompiled/function-exp-math.c) | `ev_d3faa5f00aceacc41266649d0c2fa4fee40beb1abb3295861bf4dc40b29dfe74` |
| `0x140c594c0` | [function-failure-next.c](../../decompiled/function-failure-next.c) | `ev_178ed5905a8f613499d257b4fef5982cdf9b7ddd78a11342fad5fbe2dd160772` |
| `0x140e47d30` | [function-gamma-wrapper.c](../../decompiled/function-gamma-wrapper.c) | `ev_331e815620656aa384b196cb2816a66faa1b4dadcad081e16d4044878799d9b8` |
| `0x140d8e3d0` | [function-gamma.c](../../decompiled/function-gamma.c) | `ev_27ecca58c68d5367e94df9378bd52a029bff19de39502745f710f8c4f3385bf0` |
| `0x140d8e3b0` | [function-lehmer.c](../../decompiled/function-lehmer.c) | `ev_a49803152745c867398b3b4b33362378c537e58969349577a05ba7295c9c0cc3` |
| `0x140d8e550` | [function-lognormal.c](../../decompiled/function-lognormal.c) | `ev_4a53e9519f7ec47c329c01c0a79dee1302d18741b36a61a592761f22488aeab4` |
| `0x140ddcd80` | [function-mt-seed.c](../../decompiled/function-mt-seed.c) | `ev_7f245f0b389930c7799b6b918dfdf70f0b603dd4c2b8661865b489f987617f26` |
| `0x140ea9700` | [function-mt19937.c](../../decompiled/function-mt19937.c) | `ev_97ff84c3b5675c8c52be2a12fbf4148aff9705146757b4f55f5902620ab13457` |
| `0x140e47d90` | [function-negexp.c](../../decompiled/function-negexp.c) | `ev_a9af1ea7220d83a08d55bdf59302cf0d188f7ddd48f92854010d77a9071d2f1b` |
| `0x140c4a940` | [function-normal-kernel.c](../../decompiled/function-normal-kernel.c) | `ev_2fcadc284c7cc7229cc545a6bbf962ec9028debe429c19a3c591fe8274affee8` |
| `0x140e47db0` | [function-normal-wrapper.c](../../decompiled/function-normal-wrapper.c) | `ev_b56b0f52d266234502a146b36d4f9116afe324260eb9379666a920cd03bc1f94` |
| `0x140de35b0` | [function-orchestrator.c](../../decompiled/function-orchestrator.c) | `ev_b82edb3e20f143e212dfbbc616d60a1899315db3bd490a6e8714cc7955b308c2` |
| `0x140d8e770` | [function-poisson.c](../../decompiled/function-poisson.c) | `ev_5ce902d06e6fa5783d9dda0b5ff9b1a570d8648fba4e3161664f261ca27acb6e` |
| `0x140e5e590` | [function-relative-error-formula.c](../../decompiled/function-relative-error-formula.c) | `ev_dba2b17876fd5aa6a1210c86871a519cd3a6c57d73385d4f9e9b1aa929437a3d` |
| `0x140c896b0` | [function-relative-error.c](../../decompiled/function-relative-error.c) | `ev_9f5dd9ea24bde98c951dc0271ebb2d1b27d91823c0e8836f1e8c0fb2da2db1da` |
| `0x140de2250` | [function-results-control.c](../../decompiled/function-results-control.c) | `ev_be3327cb1d2b5d59b5803180f46c3adefc77449e63d9ff5d00dee53f2f402776` |
| `0x140deab70` | [function-results-merge.c](../../decompiled/function-results-merge.c) | `ev_c8e99200ea39270ed2abc5bd3cb668da3575c40e4441fb0ee7919885b32e2b49` |
| `0x140ea97c0` | [function-rng-handler.c](../../decompiled/function-rng-handler.c) | `ev_150c6722bd463fc777d871c57d0bb0579e3fea0a8ee0bfa3f1b63a5d30d8f287` |
| `0x140de3f20` | [function-rng-next.c](../../decompiled/function-rng-next.c) | `ev_170076bd7211b4f981816e0adc2cb0464d251431faa66e35286387c2f8f8787f` |
| `0x140de0e40` | [function-rng-seed.c](../../decompiled/function-rng-seed.c) | `ev_3279160e3e1df34de9cb7619b5553597627aae217c4aa7a98f87dac5f574aae1` |
| `0x140ea9830` | [function-seed-allocation.c](../../decompiled/function-seed-allocation.c) | `ev_f8c8b4c72cc3f508e1c4eb697c8a84494a32d7cc15babead4e5623fb85250210` |
| `0x140c461c0` | [function-sim-constructor.c](../../decompiled/function-sim-constructor.c) | `ev_020c3105e7973bc8d65400d4294adfd3b43b0ce40a94d797e5c95d5e5bd85461` |
| `0x140c49300` | [function-sim-run.c](../../decompiled/function-sim-run.c) | `ev_f076daecd4abfd920a5795a6dd4e34b8ccc130173cf68ed58e683ff1fc090c21` |
| `0x140de13f0` | [function-simulation-main.c](../../decompiled/function-simulation-main.c) | `ev_9c082393040fe6c5bba8cd76c4caaf41fade924158d4cdd97b3cab997f59b222` |
| `0x140deac70` | [function-stop-check.c](../../decompiled/function-stop-check.c) | `ev_f10ed10d9391f53b5511d81458484f6ecdb738eddc182e11a14f2f83530905e4` |
| `0x140deb150` | [function-threshold-setup.c](../../decompiled/function-threshold-setup.c) | `ev_9da8a8976a5a48a3a984ee0af1da6fb65eac24364df8b87f824b7413a9c5d5ea` |
| `0x140c4a9e0` | [function-triangular-sim.c](../../decompiled/function-triangular-sim.c) | `ev_2a885c8fdde0d77fd2503fcb4735d5bf0c6a7d9e1918a17cc3ca4fbeb7794c72` |
| `0x140e47e00` | [function-triangular-wrapper.c](../../decompiled/function-triangular-wrapper.c) | `ev_5bcb9020d261d47df3a0a1468b83d2af4fc4a2a7e0aa552ce8dcb0d95c6cc788` |
| `0x140d8eb10` | [function-triangular.c](../../decompiled/function-triangular.c) | `ev_6f069bebe199a312e18fe3073ea3a92e3af8cb3c624d627fe03a1aa27ffeaee7` |
| `0x140c4aa00` | [function-uniform.c](../../decompiled/function-uniform.c) | `ev_6aee9c5574b0e2f0807df0e3f484568679634caac40d3c0ae55bf79909e1ed26` |
| `0x140e47e30` | [function-user-distribution.c](../../decompiled/function-user-distribution.c) | `ev_87379b1c0a32c6fe4ce8807de5f98e2f8c4af874cbe1b9e7f638500c7a0e44c3` |
| `0x140de2ba0` | [function-worker.c](../../decompiled/function-worker.c) | `ev_9467e44963f1b51950bf5345d456d4062612d877a64962c3fb3ebef7cb922024` |
