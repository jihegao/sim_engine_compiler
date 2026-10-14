/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-simulation-main.json
 * Evidence: ev_9c082393040fe6c5bba8cd76c4caaf41fade924158d4cdd97b3cab997f59b222
 */


/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Removing unreachable block (ram,0x000140de14ae) */
/* WARNING: Removing unreachable block (ram,0x000140de14b4) */

undefined8 FUN_140de13f0(longlong param_1,undefined8 param_2)

{
  int *piVar1;
  longlong *plVar2;
  int iVar3;
  longlong *plVar4;
  longlong lVar5;
  void *pvVar6;
  undefined8 uVar7;
  undefined8 *puVar8;
  undefined1 *puVar9;
  undefined1 auStack_158 [32];
  longlong local_138;
  undefined8 *local_130;
  undefined1 local_128 [8];
  undefined8 local_120;
  longlong *plStack_118;
  longlong local_110;
  longlong *local_108;
  undefined8 local_100;
  longlong *plStack_f8;
  undefined8 local_f0;
  undefined8 uStack_e8;
  undefined8 local_e0;
  undefined8 uStack_d8;
  undefined1 local_d0 [16];
  undefined8 local_c0;
  undefined8 local_b8;
  undefined1 local_b0 [16];
  undefined8 local_a0;
  undefined8 local_98;
  undefined8 local_90;
  void *local_88;
  undefined1 local_80;
  undefined7 uStack_7f;
  undefined8 local_70;
  ulonglong local_68;
  void *local_60 [3];
  ulonglong local_48;
  void *local_40 [3];
  ulonglong local_28;
  ulonglong local_20;
  
  local_90 = 0xfffffffffffffffe;
  local_20 = DAT_141ce8fd0 ^ (ulonglong)auStack_158;
  pvVar6 = operator_new(0x10);
  uVar7 = 0;
  local_88 = pvVar6;
  if (pvVar6 != (void *)0x0) {
    local_f0 = 0;
    uStack_e8 = 0;
    uVar7 = *(undefined8 *)(param_1 + 0xe0);
    if (*(longlong *)(param_1 + 0xe8) != 0) {
      LOCK();
      piVar1 = (int *)(*(longlong *)(param_1 + 0xe8) + 8);
      *piVar1 = *piVar1 + 1;
      UNLOCK();
    }
    thunk_FUN_140318df0(&local_f0,uVar7);
    uVar7 = FUN_140878000(pvVar6,&local_f0);
  }
  local_120 = 0;
  plStack_118 = (longlong *)0x0;
  thunk_FUN_1402ba820(&local_120,uVar7);
  if (plStack_118 != (longlong *)0x0) {
    LOCK();
    *(int *)((longlong)plStack_118 + 0xc) = *(int *)((longlong)plStack_118 + 0xc) + 1;
    UNLOCK();
  }
  plStack_f8 = plStack_118;
  local_100 = local_120;
  FUN_14087ad60(*(undefined8 *)(param_1 + 0x1f0),&local_100);
  local_68 = 0xf;
  local_70 = 0;
  local_80 = 0;
  thunk_FUN_140319190(&local_80,"Starting simulation...",0x16);
  plVar4 = *(longlong **)(param_1 + 0xe0);
  if (plVar4 != (longlong *)0x0) {
    puVar9 = &local_80;
    if (0xf < local_68) {
      puVar9 = (undefined1 *)CONCAT71(uStack_7f,local_80);
    }
    (**(code **)(*plVar4 + 0x10))(plVar4,puVar9);
  }
  if (0xf < local_68) {
    free((void *)CONCAT71(uStack_7f,local_80));
  }
  FUN_14124fd60(local_128);
  FUN_14124ffc0(local_128);
  local_e0 = 0;
  uStack_d8 = 0;
  uVar7 = *(undefined8 *)(param_1 + 0x1f0);
  if (*(longlong *)(param_1 + 0x1f8) != 0) {
    LOCK();
    piVar1 = (int *)(*(longlong *)(param_1 + 0x1f8) + 8);
    *piVar1 = *piVar1 + 1;
    UNLOCK();
  }
  thunk_FUN_140467600(&local_e0,uVar7);
  local_138 = param_1 + 0x108;
  local_130 = &local_e0;
  FUN_140de35b0(param_1 + 0x140,&local_110,param_2,param_1 + 0x18);
  local_98 = 0xf;
  local_a0 = 0;
  local_b0[0] = 0;
  thunk_FUN_140319190(local_b0,"Simulation time: ",0x11);
  puVar8 = (undefined8 *)FUN_14124fdd0(local_128,local_60,local_b0);
  plVar4 = *(longlong **)(param_1 + 0xe0);
  if (plVar4 != (longlong *)0x0) {
    if (0xf < (ulonglong)puVar8[3]) {
      puVar8 = (undefined8 *)*puVar8;
    }
    (**(code **)(*plVar4 + 0x10))(plVar4,puVar8);
  }
  if (0xf < local_48) {
    free(local_60[0]);
  }
  if (local_110 != 0) {
    if (*(char *)(param_1 + 0x200) == '\0') {
      FUN_14124ffc0(local_128);
      FUN_140de1760(param_1,local_110);
      local_b8 = 0xf;
      local_c0 = 0;
      local_d0[0] = 0;
      thunk_FUN_140319190(local_d0,"Result saving time: ",0x14);
      puVar8 = (undefined8 *)FUN_14124fdd0(local_128,local_40,local_d0);
      plVar4 = *(longlong **)(param_1 + 0xe0);
      if (plVar4 != (longlong *)0x0) {
        if (0xf < (ulonglong)puVar8[3]) {
          puVar8 = (undefined8 *)*puVar8;
        }
        (**(code **)(*plVar4 + 0x10))(plVar4,puVar8);
      }
      if (0xf < local_28) {
        free(local_40[0]);
      }
    }
    if (*(char *)(param_1 + 0x200) == '\0') {
      uVar7 = 1;
      goto LAB_140de16c6;
    }
  }
  uVar7 = 0;
LAB_140de16c6:
  plVar4 = local_108;
  if (local_108 != (longlong *)0x0) {
    LOCK();
    plVar2 = local_108 + 1;
    lVar5 = *plVar2;
    *(int *)plVar2 = (int)*plVar2 + -1;
    UNLOCK();
    if ((int)lVar5 == 1) {
      (**(code **)*local_108)(local_108);
      LOCK();
      piVar1 = (int *)((longlong)plVar4 + 0xc);
      iVar3 = *piVar1;
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (iVar3 == 1) {
        (**(code **)(*local_108 + 8))();
      }
    }
  }
  plVar4 = plStack_118;
  if (plStack_118 != (longlong *)0x0) {
    LOCK();
    plVar2 = plStack_118 + 1;
    lVar5 = *plVar2;
    *(int *)plVar2 = (int)*plVar2 + -1;
    UNLOCK();
    if ((int)lVar5 == 1) {
      (**(code **)*plStack_118)(plStack_118);
      LOCK();
      piVar1 = (int *)((longlong)plVar4 + 0xc);
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (*piVar1 == 0) {
        (**(code **)(*plStack_118 + 8))();
      }
    }
  }
  return uVar7;
}


