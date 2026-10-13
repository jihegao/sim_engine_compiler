/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-failure-next.json
 * Evidence: ev_178ed5905a8f613499d257b4fef5982cdf9b7ddd78a11342fad5fbe2dd160772
 */


void FUN_140c594c0(longlong param_1,undefined4 param_2)

{
  longlong lVar1;
  int iVar2;
  undefined8 *puVar3;
  longlong *plVar4;
  
  lVar1 = FUN_140c484e0(*(undefined8 *)(param_1 + 0x70));
  if (lVar1 != 0) {
    puVar3 = (undefined8 *)FUN_140c484e0(*(undefined8 *)(param_1 + 0x70));
    iVar2 = (**(code **)*puVar3)(puVar3);
    if (1 < iVar2) {
      FUN_140c48bc0(*(undefined8 *)(param_1 + 0x70));
      FUN_140c59b60(*(undefined8 *)(param_1 + 0x68));
      plVar4 = (longlong *)FUN_140c484e0(*(undefined8 *)(param_1 + 0x70));
      (**(code **)(*plVar4 + 0x10))(plVar4," Next random failure will occur ");
      plVar4 = (longlong *)FUN_140c484e0(*(undefined8 *)(param_1 + 0x70));
      (**(code **)(*plVar4 + 0x20))(plVar4,param_2);
      plVar4 = (longlong *)FUN_140c484e0(*(undefined8 *)(param_1 + 0x70));
      (**(code **)(*plVar4 + 8))(plVar4);
    }
  }
  return;
}


