/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-worker.json
 * Evidence: ev_9467e44963f1b51950bf5345d456d4062612d877a64962c3fb3ebef7cb922024
 */


/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */

void FUN_140de2ba0(longlong param_1,undefined8 param_2,longlong param_3,undefined8 *param_4,
                  longlong *param_5)

{
  int *piVar1;
  longlong *plVar2;
  undefined8 *puVar3;
  int iVar4;
  undefined8 uVar5;
  undefined8 uVar6;
  longlong *plVar7;
  longlong lVar8;
  longlong *plVar9;
  int iVar10;
  undefined4 uVar11;
  undefined4 uVar12;
  undefined1 auStack_5b8 [32];
  undefined4 *local_598;
  undefined4 *local_590;
  undefined8 local_588;
  undefined8 local_580;
  undefined8 local_578;
  undefined8 local_570;
  undefined1 local_568;
  undefined4 local_558;
  undefined4 local_554;
  int local_550 [2];
  undefined8 *local_548;
  longlong *local_540;
  undefined8 *local_538;
  undefined8 *local_530 [2];
  longlong *local_520;
  undefined8 local_518;
  undefined4 local_510;
  undefined4 local_50c;
  undefined4 local_508 [2];
  longlong local_500;
  longlong *local_4f8;
  char local_4f0;
  longlong *local_4e0;
  char local_4d8;
  undefined8 local_4d0;
  longlong local_4c8;
  longlong local_4c0;
  longlong *local_4b8;
  char local_4b0;
  undefined8 local_4a8;
  undefined8 *local_4a0;
  longlong *local_498;
  undefined8 local_490;
  longlong *local_488;
  undefined8 *local_480;
  longlong *local_470;
  undefined4 local_468 [2];
  undefined **local_460;
  undefined4 local_438 [2];
  undefined **local_430;
  undefined4 local_428 [2];
  undefined **local_420;
  longlong *local_410;
  undefined8 local_408;
  undefined8 uStack_400;
  undefined4 local_3f8 [2];
  undefined **local_3f0;
  undefined1 local_3e8 [8];
  longlong *local_3e0;
  undefined1 local_3d8 [8];
  undefined8 local_3d0;
  undefined1 local_3c8 [64];
  undefined1 local_388 [416];
  undefined1 local_1e8 [416];
  ulonglong local_48;
  
  local_3d0 = 0xfffffffffffffffe;
  local_48 = DAT_141ce8fd0 ^ (ulonglong)auStack_5b8;
  local_488 = param_5;
  local_538 = param_4;
  local_500 = param_1;
  local_4d0 = param_2;
  local_4c8 = param_3;
  local_4c0 = param_3;
  local_480 = param_4;
  local_4a8 = FUN_140d39bb0(param_2);
  local_550[0] = *(int *)*param_5;
  FUN_140dd0370(local_530,param_2);
  uVar11 = 0;
  do {
    FUN_140de3f30(*param_5,&local_4f8);
    local_558 = 0;
    lVar8 = *param_5;
    *(int *)(lVar8 + 4) = *(int *)(lVar8 + 4) + 1;
    if (*(int *)(lVar8 + 4) == 1) {
      local_558 = *(undefined4 *)(lVar8 + 0x28);
      iVar4 = *(int *)(lVar8 + 0x2c);
    }
    else {
      iVar4 = FUN_140ea9830(*(undefined8 *)(lVar8 + 0x30),uVar11,&local_558,lVar8 + 8);
      *(int *)(lVar8 + 0x2c) = iVar4;
    }
    plVar7 = local_4f8;
    uVar11 = *(undefined4 *)(lVar8 + 8);
    if (iVar4 == 0) {
      local_408 = 0;
      uStack_400 = 0;
      if ((local_4f8 == (longlong *)0x0) || ((local_4f0 != '\0' && ((char)local_4f8[8] != '\0')))) {
        local_428[0] = 4;
        local_420 = &PTR_vftable_141ce04c0;
                    /* WARNING: Subroutine does not return */
        FUN_1412211d8(local_428);
      }
      local_4e0 = local_4f8 + 6;
      local_4d8 = 0;
      iVar4 = FUN_1412230cc();
      if (iVar4 != 0) {
        FUN_141223240(iVar4);
      }
      local_4d8 = '\x01';
      if (*(char *)((longlong)plVar7 + 0x49) != '\0') {
        local_3f8[0] = 3;
        local_3f0 = &PTR_vftable_141ce04c0;
                    /* WARNING: Subroutine does not return */
        FUN_1412211d8(local_3f8);
      }
      uStack_400 = 0;
      local_408 = 0;
      plVar9 = (longlong *)plVar7[3];
      plVar7[3] = 0;
      plVar7[2] = 0;
      local_470 = plVar9;
      if (plVar9 != (longlong *)0x0) {
        LOCK();
        plVar2 = plVar9 + 1;
        *(int *)plVar2 = (int)*plVar2 + -1;
        UNLOCK();
        plVar7 = local_4f8;
        if ((int)*plVar2 == 0) {
          (**(code **)*plVar9)(plVar9);
          LOCK();
          piVar1 = (int *)((longlong)plVar9 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          plVar7 = local_4f8;
          if (*piVar1 == 0) {
            (**(code **)(*local_470 + 8))();
            plVar7 = local_4f8;
          }
        }
      }
      (**(code **)(*plVar7 + 0x20))(plVar7,&local_4e0,0);
      if ((local_4d8 != '\0') && (iVar4 = _Mtx_unlock(local_4e0), iVar4 != 0)) {
        FUN_141223240(iVar4);
      }
      FUN_140dde970(&local_4f8);
      plVar7 = (longlong *)*local_520;
      *local_520 = (longlong)local_520;
      local_520[1] = (longlong)local_520;
      local_518 = 0;
      if (plVar7 != local_520) {
        do {
          plVar9 = (longlong *)*plVar7;
          free(plVar7);
          plVar7 = plVar9;
        } while (plVar9 != local_520);
      }
      free(local_520);
      thunk_FUN_140467f40(local_530,local_3d8,*local_530[0],local_530[0]);
      free(local_530[0]);
      plVar7 = *(longlong **)(local_4c8 + 8);
      if (plVar7 != (longlong *)0x0) {
        LOCK();
        plVar9 = plVar7 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*plVar7)(plVar7);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
      plVar7 = (longlong *)local_538[1];
      if (plVar7 != (longlong *)0x0) {
        LOCK();
        plVar9 = plVar7 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*plVar7)(plVar7);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
      plVar7 = (longlong *)param_5[1];
      if (plVar7 == (longlong *)0x0) {
        return;
      }
      LOCK();
      plVar9 = plVar7 + 1;
      *(int *)plVar9 = (int)*plVar9 + -1;
      UNLOCK();
      if ((int)*plVar9 != 0) {
        return;
      }
      (**(code **)*plVar7)(plVar7);
      LOCK();
      piVar1 = (int *)((longlong)plVar7 + 0xc);
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (*piVar1 != 0) {
        return;
      }
      (**(code **)(*plVar7 + 8))(plVar7);
      return;
    }
    local_50c = FUN_140d39d80(param_2);
    local_508[0] = FUN_140d3aff0(param_2);
    local_510 = FUN_140d3af80(param_2);
    local_490 = FUN_140c8b3a0(local_4a8);
    local_590 = &local_50c;
    local_598 = local_508;
    FUN_140ddaae0(&local_548,&local_490,local_550,&local_510);
    FUN_140dd50b0(*(undefined8 *)(local_500 + 8),local_548);
    local_580 = FUN_140de1bd0(*param_5);
    lVar8 = *param_5;
    if (*(int *)(lVar8 + 0x2c) == 1) {
      local_570 = *(undefined8 *)(lVar8 + 0x48);
    }
    else {
      local_570 = 0;
    }
    if (*(int *)(lVar8 + 0x2c) == 1) {
      local_578 = *(undefined8 *)(lVar8 + 0x38);
    }
    else {
      local_578 = 0;
    }
    local_588 = *local_538;
    local_568 = 1;
    local_590 = (undefined4 *)CONCAT44(local_590._4_4_,uVar11);
    local_598 = (undefined4 *)CONCAT44(local_598._4_4_,local_558);
    FUN_140c461c0(local_388,param_2,local_530,local_548);
    uVar5 = FUN_140d39bb0(param_2);
    uVar12 = FUN_140c8b3a0(uVar5);
    FUN_140c49300(local_388,uVar12);
    local_554 = FUN_140c489b0(local_388);
    (**(code **)*local_548)(local_548,uVar11,local_558);
    puVar3 = local_548;
    uVar5 = FUN_140c89770(local_548);
    uVar6 = FUN_140c896f0(puVar3);
    lVar8 = local_500;
    FUN_140de1260(local_500,uVar11,uVar6,uVar5);
    FUN_140c47540(local_388);
    for (iVar10 = 1; iVar10 < local_550[0]; iVar10 = iVar10 + 1) {
      lVar8 = *param_5;
      *(int *)(lVar8 + 4) = *(int *)(lVar8 + 4) + 1;
      if (*(int *)(lVar8 + 4) == 1) {
        local_558 = *(undefined4 *)(lVar8 + 0x28);
        iVar4 = *(int *)(lVar8 + 0x2c);
      }
      else {
        iVar4 = FUN_140ea9830(*(undefined8 *)(lVar8 + 0x30),local_554,&local_558,lVar8 + 8);
        *(int *)(lVar8 + 0x2c) = iVar4;
      }
      uVar11 = *(undefined4 *)(lVar8 + 8);
      if (iVar4 == 0) goto LAB_140de324f;
      local_580 = FUN_140de1bd0(*param_5);
      uVar5 = local_4d0;
      lVar8 = *param_5;
      if (*(int *)(lVar8 + 0x2c) == 1) {
        local_570 = *(undefined8 *)(lVar8 + 0x48);
      }
      else {
        local_570 = 0;
      }
      if (*(int *)(lVar8 + 0x2c) == 1) {
        local_578 = *(undefined8 *)(lVar8 + 0x38);
      }
      else {
        local_578 = 0;
      }
      local_588 = *local_538;
      local_568 = 1;
      local_590 = (undefined4 *)CONCAT44(local_590._4_4_,uVar11);
      local_598 = (undefined4 *)CONCAT44(local_598._4_4_,local_558);
      FUN_140c461c0(local_1e8,local_4d0,local_530,local_548);
      uVar5 = FUN_140d39bb0(uVar5);
      uVar12 = FUN_140c8b3a0(uVar5);
      FUN_140c49300(local_1e8,uVar12);
      local_554 = FUN_140c489b0(local_1e8);
      (**(code **)*local_548)(local_548,uVar11,local_558);
      puVar3 = local_548;
      uVar5 = FUN_140c89770(local_548);
      uVar6 = FUN_140c896f0(puVar3);
      lVar8 = local_500;
      FUN_140de1260(local_500,uVar11,uVar6,uVar5);
      FUN_140c47540(local_1e8);
    }
    if (iVar4 != 0) {
      uVar5 = FUN_140de19e0(lVar8,local_3e8);
      FUN_140ddfc10(param_5,uVar5);
      plVar7 = local_3e0;
      if (local_3e0 != (longlong *)0x0) {
        LOCK();
        plVar9 = local_3e0 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*local_3e0)(local_3e0);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
    }
LAB_140de324f:
    plVar9 = local_4f8;
    plVar7 = local_540;
    puVar3 = local_548;
    if (local_540 != (longlong *)0x0) {
      LOCK();
      *(int *)(local_540 + 1) = (int)local_540[1] + 1;
      UNLOCK();
    }
    local_498 = local_540;
    local_4a0 = local_548;
    if ((local_4f8 == (longlong *)0x0) || ((local_4f0 != '\0' && ((char)local_4f8[8] != '\0')))) {
      local_468[0] = 4;
      local_460 = &PTR_vftable_141ce04c0;
                    /* WARNING: Subroutine does not return */
      FUN_1412211d8(local_468);
    }
    local_4b8 = local_4f8 + 6;
    local_4b0 = 0;
    iVar10 = FUN_1412230cc();
    if (iVar10 != 0) {
      FUN_141223240(iVar10);
    }
    local_4b0 = '\x01';
    if (*(char *)((longlong)plVar9 + 0x49) != '\0') {
      local_438[0] = 3;
      local_430 = &PTR_vftable_141ce04c0;
                    /* WARNING: Subroutine does not return */
      FUN_1412211d8(local_438);
    }
    local_498 = (longlong *)0x0;
    local_4a0 = (undefined8 *)0x0;
    plVar2 = (longlong *)plVar9[3];
    plVar9[3] = (longlong)plVar7;
    plVar9[2] = (longlong)puVar3;
    local_410 = plVar2;
    if (plVar2 != (longlong *)0x0) {
      LOCK();
      plVar7 = plVar2 + 1;
      *(int *)plVar7 = (int)*plVar7 + -1;
      UNLOCK();
      plVar9 = local_4f8;
      if ((int)*plVar7 == 0) {
        (**(code **)*plVar2)(plVar2);
        LOCK();
        piVar1 = (int *)((longlong)plVar2 + 0xc);
        *piVar1 = *piVar1 + -1;
        UNLOCK();
        plVar9 = local_4f8;
        if (*piVar1 == 0) {
          (**(code **)(*local_410 + 8))();
          plVar9 = local_4f8;
        }
      }
    }
    (**(code **)(*plVar9 + 0x20))(plVar9,&local_4b8,0);
    if ((local_4b0 != '\0') && (iVar10 = _Mtx_unlock(local_4b8), iVar10 != 0)) {
      FUN_141223240(iVar10);
    }
    plVar7 = local_540;
    if (iVar4 == 0) {
      if (local_540 != (longlong *)0x0) {
        LOCK();
        plVar7 = local_540 + 1;
        *(int *)plVar7 = (int)*plVar7 + -1;
        UNLOCK();
        if ((int)*plVar7 == 0) {
          (**(code **)*local_540)(local_540);
          LOCK();
          piVar1 = (int *)((longlong)local_540 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*local_540 + 8))(local_540);
          }
        }
      }
      FUN_140dde970(&local_4f8);
      plVar7 = (longlong *)*local_520;
      *local_520 = (longlong)local_520;
      local_520[1] = (longlong)local_520;
      local_518 = 0;
      if (plVar7 != local_520) {
        do {
          plVar9 = (longlong *)*plVar7;
          free(plVar7);
          plVar7 = plVar9;
        } while (plVar9 != local_520);
      }
      free(local_520);
      thunk_FUN_140467f40(local_530,local_3c8,*local_530[0],local_530[0]);
      free(local_530[0]);
      plVar7 = *(longlong **)(local_4c8 + 8);
      if (plVar7 != (longlong *)0x0) {
        LOCK();
        plVar9 = plVar7 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*plVar7)(plVar7);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
      plVar7 = (longlong *)local_538[1];
      if (plVar7 != (longlong *)0x0) {
        LOCK();
        plVar9 = plVar7 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*plVar7)(plVar7);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
      plVar7 = (longlong *)param_5[1];
      if (plVar7 != (longlong *)0x0) {
        LOCK();
        plVar9 = plVar7 + 1;
        *(int *)plVar9 = (int)*plVar9 + -1;
        UNLOCK();
        if ((int)*plVar9 == 0) {
          (**(code **)*plVar7)(plVar7);
          LOCK();
          piVar1 = (int *)((longlong)plVar7 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar7 + 8))(plVar7);
          }
        }
      }
      return;
    }
    if (local_540 != (longlong *)0x0) {
      LOCK();
      plVar9 = local_540 + 1;
      *(int *)plVar9 = (int)*plVar9 + -1;
      UNLOCK();
      if ((int)*plVar9 == 0) {
        (**(code **)*local_540)(local_540);
        LOCK();
        piVar1 = (int *)((longlong)plVar7 + 0xc);
        *piVar1 = *piVar1 + -1;
        UNLOCK();
        if (*piVar1 == 0) {
          (**(code **)(*plVar7 + 8))(plVar7);
        }
      }
    }
    FUN_140dde970(&local_4f8);
    param_2 = local_4d0;
    uVar11 = local_554;
  } while( true );
}


