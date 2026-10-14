/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-event-loop.json
 * Evidence: ev_1165eef43fbca2663726b7825f9f5c507df71525a5dd3b00a7ac5bdc06997053
 */


void FUN_140d8e8f0(undefined4 *param_1)

{
  int iVar1;
  longlong *plVar2;
  longlong lVar3;
  
  if (param_1[0x1b] == 0) {
    iVar1 = param_1[0x1a];
    while ((iVar1 == 0 &&
           (lVar3 = FUN_140d8e390(param_1),
           *(longlong *)(lVar3 + 0x30) != *(longlong *)(param_1 + 2)))) {
      param_1[0x1b] = 1;
      lVar3 = 0;
      if (-1 < (int)param_1[0x10]) {
        lVar3 = **(longlong **)(param_1 + 0xc);
      }
      *(longlong *)(param_1 + 6) = lVar3;
      *param_1 = 0;
      *(undefined8 *)(param_1 + 4) = *(undefined8 *)(lVar3 + 0x30);
      *(undefined8 *)(param_1 + 8) = *(undefined8 *)(lVar3 + 0x18);
      FUN_140e970f0();
      (**(code **)(**(longlong **)(param_1 + 4) + 0x10))();
      if (*(longlong *)(param_1 + 6) != 0) {
        *(undefined8 *)(*(longlong *)(*(longlong *)(param_1 + 6) + 0x30) + 0x30) = 0;
        plVar2 = *(longlong **)(param_1 + 6);
        if (plVar2 != (longlong *)0x0) {
          (**(code **)(*plVar2 + 0x18))(plVar2,1);
        }
        *(undefined8 *)(param_1 + 6) = 0;
      }
      iVar1 = param_1[0x1a];
    }
    param_1[0x1b] = 0;
  }
  return;
}


