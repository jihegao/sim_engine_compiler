/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-seed-allocation.json
 * Evidence: ev_f8c8b4c72cc3f508e1c4eb697c8a84494a32d7cc15babead4e5623fb85250210
 */


char FUN_140ea9830(undefined8 *param_1,undefined4 param_2,undefined4 *param_3,undefined4 *param_4)

{
  int iVar1;
  undefined4 uVar2;
  char cVar3;
  
  iVar1 = FUN_1412230cc(param_1 + 1);
  if (iVar1 != 0) {
    FUN_141223240(iVar1);
  }
  cVar3 = '\0';
  if ((*(char *)((longlong)param_1 + 0x1c) == '\0') &&
     (*(uint *)(param_1 + 3) < *(uint *)(param_1 + 2))) {
    if (*(uint *)(param_1 + 3) == 0) {
      uVar2 = *(undefined4 *)((longlong)param_1 + 0x14);
    }
    else {
      uVar2 = (**(code **)*param_1)(param_1,param_2);
    }
    *param_3 = uVar2;
    *(int *)(param_1 + 3) = *(int *)(param_1 + 3) + 1;
    *param_4 = *(undefined4 *)(param_1 + 3);
    cVar3 = (*(int *)(param_1 + 3) != 1) + '\x01';
  }
  iVar1 = _Mtx_unlock(param_1 + 1);
  if (iVar1 != 0) {
    FUN_141223240(iVar1);
  }
  return cVar3;
}


