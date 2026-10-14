/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-mt-seed.json
 * Evidence: ev_7f245f0b389930c7799b6b918dfdf70f0b603dd4c2b8661865b489f987617f26
 */


undefined8 * FUN_140ddcd80(undefined8 *param_1,undefined8 param_2,uint param_3)

{
  int iVar1;
  uint *puVar2;
  longlong lVar3;
  
  FUN_140ea9600();
  iVar1 = 1;
  *param_1 = CMersenneTwisterSeedHandler::vftable;
  *(undefined4 *)((longlong)param_1 + 0x13a4) = 0xffffffff;
  *(uint *)((longlong)param_1 + 0x24) = param_3;
  lVar3 = 0x26f;
  puVar2 = (uint *)(param_1 + 5);
  do {
    param_3 = (param_3 >> 0x1e ^ param_3) * 0x6c078965 + iVar1;
    iVar1 = iVar1 + 1;
    *puVar2 = param_3;
    lVar3 = lVar3 + -1;
    puVar2 = puVar2 + 1;
  } while (lVar3 != 0);
  *(undefined4 *)(param_1 + 4) = 0x270;
  return param_1;
}


