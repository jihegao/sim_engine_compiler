/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-results-control.json
 * Evidence: ev_be3327cb1d2b5d59b5803180f46c3adefc77449e63d9ff5d00dee53f2f402776
 */


/* WARNING: Removing unreachable block (ram,0x000140de24b0) */
/* WARNING: Removing unreachable block (ram,0x000140de24bb) */
/* WARNING: Removing unreachable block (ram,0x000140de24ce) */

void FUN_140de2250(longlong *param_1,undefined8 param_2,undefined8 param_3,undefined8 param_4)

{
  int *piVar1;
  undefined8 **ppuVar2;
  undefined8 *puVar3;
  undefined8 *puVar4;
  longlong *plVar5;
  longlong lVar6;
  char cVar7;
  int iVar8;
  longlong *plVar9;
  longlong lVar10;
  longlong *plVar11;
  undefined8 uVar12;
  undefined8 uVar13;
  undefined8 *local_98;
  undefined1 local_90;
  longlong local_88;
  longlong *plStack_80;
  undefined8 local_78;
  char local_70;
  longlong local_68;
  longlong *plStack_60;
  undefined8 local_58;
  longlong *plStack_50;
  undefined1 local_48 [8];
  longlong *local_40;
  undefined8 local_38;
  undefined1 local_30 [24];
  
  local_38 = 0xfffffffffffffffe;
  local_58 = 0;
  plStack_50 = (longlong *)0x0;
  while( true ) {
    local_98 = (undefined8 *)0x0;
    local_90 = 0;
    uVar12 = 0;
    uVar13 = 0;
    FUN_140de1960(param_1,&local_78);
    if (param_1[6] == 0) break;
    plVar9 = (longlong *)FUN_140de9100(param_1 + 2,local_30);
    lVar10 = 0;
    if ((longlong *)*plVar9 != (longlong *)0x0) {
      lVar10 = *(longlong *)*plVar9;
    }
    ppuVar2 = *(undefined8 ***)
               (*(longlong *)(lVar10 + 8) + (*(longlong *)(lVar10 + 0x10) - 1U & plVar9[2]) * 8);
    if (&local_98 != ppuVar2) {
      local_98 = *ppuVar2;
      *ppuVar2 = (undefined8 *)0x0;
      local_90 = *(undefined1 *)(ppuVar2 + 1);
    }
    puVar3 = (undefined8 *)**(longlong **)(param_1[3] + (param_1[4] - 1U & param_1[5]) * 8);
    if (puVar3 != (undefined8 *)0x0) {
      LOCK();
      piVar1 = (int *)(puVar3 + 1);
      iVar8 = *piVar1;
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (iVar8 == 1) {
        puVar4 = (undefined8 *)puVar3[10];
        if (puVar4 == (undefined8 *)0x0) {
          (**(code **)*puVar3)(puVar3,1,0,param_4,uVar12,uVar13);
        }
        else {
          (**(code **)*puVar4)(puVar4,puVar3);
        }
      }
    }
    plVar9 = param_1 + 6;
    *plVar9 = *plVar9 + -1;
    if (*plVar9 == 0) {
      param_1[5] = 0;
    }
    else {
      param_1[5] = param_1[5] + 1;
    }
    if ((local_70 != '\0') && (iVar8 = _Mtx_unlock(local_78), iVar8 != 0)) {
      FUN_141223240(iVar8);
    }
    plVar11 = (longlong *)FUN_140de9470(&local_98,local_48);
    plVar9 = local_40;
    local_88 = 0;
    plStack_80 = (longlong *)0x0;
    if (&local_88 != plVar11) {
      plStack_80 = (longlong *)plVar11[1];
      plVar11[1] = 0;
      local_88 = *plVar11;
      *plVar11 = 0;
    }
    lVar10 = local_88;
    plVar11 = plStack_80;
    if (local_40 != (longlong *)0x0) {
      LOCK();
      plVar5 = local_40 + 1;
      lVar6 = *plVar5;
      *(int *)plVar5 = (int)*plVar5 + -1;
      UNLOCK();
      if ((int)lVar6 == 1) {
        (**(code **)*local_40)(local_40);
        LOCK();
        piVar1 = (int *)((longlong)plVar9 + 0xc);
        iVar8 = *piVar1;
        *piVar1 = *piVar1 + -1;
        UNLOCK();
        if (iVar8 == 1) {
          (**(code **)(*plVar9 + 8))(plVar9);
        }
      }
    }
    plVar9 = plVar11;
    if (lVar10 != 0) {
      plVar5 = (longlong *)param_1[7];
      if (plVar11 != (longlong *)0x0) {
        LOCK();
        *(int *)(plVar11 + 1) = (int)plVar11[1] + 1;
        UNLOCK();
      }
      local_68 = lVar10;
      plStack_60 = plVar11;
      (**(code **)(*plVar5 + 0x18))(plVar5,&local_68);
      cVar7 = (**(code **)(*(longlong *)param_1[7] + 0x38))();
      if ((cVar7 == '\0') && (*param_1 != 0)) {
        FUN_140ea9910();
      }
    }
    if (plVar11 != (longlong *)0x0) {
      LOCK();
      plVar11 = plVar11 + 1;
      lVar10 = *plVar11;
      *(int *)plVar11 = (int)*plVar11 + -1;
      UNLOCK();
      if ((int)lVar10 == 1) {
        plVar11 = plVar9;
        (**(code **)*plVar9)(plVar9);
        LOCK();
        piVar1 = (int *)((longlong)plVar9 + 0xc);
        iVar8 = *piVar1;
        *piVar1 = *piVar1 + -1;
        UNLOCK();
        if (iVar8 == 1) {
          (**(code **)(*plVar11 + 8))();
        }
      }
    }
    if (local_98 != (undefined8 *)0x0) {
      LOCK();
      piVar1 = (int *)(local_98 + 1);
      iVar8 = *piVar1;
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (iVar8 == 1) {
        puVar3 = (undefined8 *)local_98[10];
        if (puVar3 == (undefined8 *)0x0) {
          (**(code **)*local_98)(local_98,1);
        }
        else {
          (**(code **)*puVar3)(puVar3,local_98);
        }
      }
    }
  }
  if ((local_70 != '\0') && (iVar8 = _Mtx_unlock(local_78), iVar8 != 0)) {
    FUN_141223240(iVar8);
  }
  plVar9 = plStack_50;
  if (plStack_50 != (longlong *)0x0) {
    LOCK();
    plVar11 = plStack_50 + 1;
    lVar10 = *plVar11;
    *(int *)plVar11 = (int)*plVar11 + -1;
    UNLOCK();
    if ((int)lVar10 == 1) {
      (**(code **)*plStack_50)(plStack_50);
      LOCK();
      piVar1 = (int *)((longlong)plVar9 + 0xc);
      iVar8 = *piVar1;
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (iVar8 == 1) {
        (**(code **)(*plStack_50 + 8))();
      }
    }
  }
  return;
}


