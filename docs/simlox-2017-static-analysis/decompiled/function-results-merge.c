/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-results-merge.json
 * Evidence: ev_c8e99200ea39270ed2abc5bd3cb668da3575c40e4441fb0ee7919885b32e2b49
 */


void FUN_140deab70(longlong param_1,undefined8 *param_2,undefined8 param_3,undefined8 param_4)

{
  int *piVar1;
  longlong *plVar2;
  longlong *plVar3;
  undefined8 uVar4;
  undefined1 local_50 [8];
  longlong *local_48;
  undefined1 local_40 [16];
  double local_30;
  
  if (*(longlong *)(param_1 + 0xf8) == 0) {
    uVar4 = FUN_140dea840(local_50);
    thunk_FUN_140463e30(param_1 + 0xf8,uVar4);
    if (local_48 != (longlong *)0x0) {
      LOCK();
      plVar3 = local_48 + 1;
      *(int *)plVar3 = (int)*plVar3 + -1;
      UNLOCK();
      if ((int)*plVar3 == 0) {
        (**(code **)*local_48)(local_48);
        LOCK();
        piVar1 = (int *)((longlong)local_48 + 0xc);
        *piVar1 = *piVar1 + -1;
        UNLOCK();
        if (*piVar1 == 0) {
          (**(code **)(*local_48 + 8))(local_48);
        }
      }
    }
  }
  else {
    FUN_140c88de0(*(longlong *)(param_1 + 0xf8),*param_2,param_3,param_4,0xfffffffffffffffe);
  }
  if (*(char *)(param_1 + 0x11c) != '\0') {
    FUN_140c896b0(*(undefined8 *)(param_1 + 0xf8),local_40);
    if (*(double *)(param_1 + 0x120) <= local_30) {
      *(undefined4 *)(param_1 + 0x128) = 0;
    }
    else {
      *(int *)(param_1 + 0x128) = *(int *)(param_1 + 0x128) + 1;
    }
  }
  plVar3 = (longlong *)param_2[1];
  if (plVar3 != (longlong *)0x0) {
    LOCK();
    plVar2 = plVar3 + 1;
    *(int *)plVar2 = (int)*plVar2 + -1;
    UNLOCK();
    if ((int)*plVar2 == 0) {
      (**(code **)*plVar3)(plVar3);
      LOCK();
      piVar1 = (int *)((longlong)plVar3 + 0xc);
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (*piVar1 == 0) {
        (**(code **)(*plVar3 + 8))(plVar3);
      }
    }
  }
  return;
}


