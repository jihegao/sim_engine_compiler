/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-orchestrator.json
 * Evidence: ev_b82edb3e20f143e212dfbbc616d60a1899315db3bd490a6e8714cc7955b308c2
 */


undefined8 *
FUN_140de35b0(undefined8 *param_1,undefined8 *param_2,undefined8 param_3,longlong param_4,
             undefined8 param_5,longlong param_6)

{
  longlong *plVar1;
  int *piVar2;
  ulonglong *puVar3;
  void *_Memory;
  longlong *plVar4;
  undefined4 *puVar5;
  longlong lVar6;
  undefined4 uVar7;
  char cVar8;
  undefined4 uVar9;
  undefined4 uVar10;
  uint uVar11;
  uint uVar12;
  int iVar13;
  undefined8 *puVar14;
  undefined8 uVar15;
  uint *puVar16;
  uint *puVar17;
  undefined8 uVar18;
  undefined8 uVar19;
  undefined8 *puVar20;
  undefined4 *puVar21;
  longlong lVar22;
  uint uVar23;
  ulonglong uVar24;
  uint local_res8 [2];
  undefined8 *local_res10;
  uint local_178;
  uint local_174 [3];
  undefined4 local_168;
  undefined4 uStack_164;
  int iStack_160;
  undefined4 uStack_15c;
  undefined1 local_158 [8];
  longlong *local_150;
  undefined8 *local_148;
  undefined8 *local_140;
  undefined4 local_138;
  undefined8 local_130;
  void *local_128 [2];
  longlong *local_118;
  undefined8 local_110;
  undefined8 uStack_108;
  undefined1 local_100 [8];
  longlong *local_f8;
  undefined8 local_e8;
  undefined8 uStack_e0;
  undefined4 local_d8;
  undefined4 uStack_d4;
  undefined4 uStack_d0;
  undefined4 uStack_cc;
  undefined1 local_c8 [8];
  longlong *local_c0;
  undefined4 local_b8;
  undefined4 uStack_b4;
  undefined4 uStack_b0;
  undefined4 uStack_ac;
  undefined1 local_a8 [8];
  longlong *local_a0;
  undefined8 local_98;
  undefined1 local_90 [16];
  undefined1 local_80 [16];
  longlong *local_70;
  longlong *local_60;
  longlong *local_50;
  
  local_98 = 0xfffffffffffffffe;
  uVar23 = 0;
  local_138 = 0;
  local_res10 = param_2;
  puVar14 = (undefined8 *)FUN_140ddabc0(local_128,param_4,param_5,param_3);
  puVar20 = param_1 + 1;
  if (puVar20 != puVar14) {
    uVar15 = *puVar14;
    *puVar14 = 0;
    _Memory = (void *)*puVar20;
    *puVar20 = uVar15;
    if (_Memory != (void *)0x0) {
      thunk_FUN_140463960(_Memory);
      free(_Memory);
    }
  }
  if (local_128[0] != (void *)0x0) {
    thunk_FUN_140463960(local_128[0]);
    free(local_128[0]);
  }
  uVar9 = FUN_140d3d630(param_3);
  uVar10 = FUN_140d3d600(param_3);
  puVar20 = *(undefined8 **)(param_4 + 0xd8);
  if (puVar20 != (undefined8 *)0x0) {
    puVar14 = (undefined8 *)FUN_140ddac30(&local_140);
    local_110 = 0;
    uStack_108 = 0;
    uVar15 = *puVar14;
    *puVar14 = 0;
    FUN_140dd92c0(&local_110,uVar15,0);
    (**(code **)*puVar20)(puVar20,uVar9,uVar10,&local_110);
    if (local_140 != (undefined8 *)0x0) {
      (**(code **)*local_140)(local_140,1);
    }
  }
  uVar15 = FUN_140d39bb0(param_3);
  cVar8 = FUN_140c8b270(uVar15);
  if (cVar8 == '\x01') {
    plVar4 = (longlong *)param_1[10];
    lVar22 = *plVar4;
    uVar15 = FUN_140d39bb0(param_3);
    uVar9 = FUN_140c8b3a0(uVar15);
    (**(code **)(lVar22 + 0x28))(plVar4,uVar9);
  }
  else {
    plVar4 = (longlong *)param_1[0xb];
    param_1[0xb] = 0;
    param_1[10] = 0;
    local_118 = plVar4;
    if (plVar4 != (longlong *)0x0) {
      LOCK();
      plVar1 = plVar4 + 1;
      *(int *)plVar1 = (int)*plVar1 + -1;
      UNLOCK();
      if ((int)*plVar1 == 0) {
        (**(code **)*plVar4)(plVar4);
        LOCK();
        piVar2 = (int *)((longlong)plVar4 + 0xc);
        *piVar2 = *piVar2 + -1;
        UNLOCK();
        if (*piVar2 == 0) {
          (**(code **)(*local_118 + 8))();
        }
      }
    }
  }
  plVar4 = (longlong *)param_1[0xc];
  if (plVar4 != (longlong *)0x0) {
    lVar22 = *plVar4;
    uVar15 = FUN_140d39bb0(param_3);
    uVar9 = FUN_140c8b3a0(uVar15);
    (**(code **)(lVar22 + 0x28))(plVar4,uVar9);
  }
  FUN_140de2020(param_1,param_3,param_4);
  uVar15 = FUN_140d39bb0(param_3);
  uVar11 = FUN_140c8b2c0(uVar15);
  uVar12 = 1;
  local_res8[0] = 1;
  local_178 = uVar11;
  cVar8 = (**(code **)(*(longlong *)*param_1 + 0x10))();
  if (cVar8 != '\0') {
    uVar12 = FID_conflict_GetCoreCount();
    local_res8[0] = uVar12;
  }
  local_174[1] = 1;
  puVar16 = local_res8;
  if (*(uint *)(param_4 + 0xe8) < uVar12) {
    puVar16 = (uint *)(param_4 + 0xe8);
  }
  puVar17 = local_174 + 1;
  if (1 < *puVar16) {
    puVar17 = puVar16;
  }
  puVar16 = &local_178;
  if (*puVar17 < uVar11) {
    puVar16 = puVar17;
  }
  uVar12 = *puVar16;
  local_174[0] = (**(code **)(*(longlong *)param_1[7] + 0x30))();
  puVar16 = (uint *)(param_1 + 0x10);
  *puVar16 = uVar11;
  if (1 < uVar12) {
    *puVar16 = uVar11 / (uVar12 * uVar12) + uVar11 / uVar12;
  }
  puVar17 = local_174;
  if (*puVar16 <= local_174[0]) {
    puVar17 = puVar16;
  }
  *puVar16 = *puVar17;
  if (uVar12 != 0) {
    puVar3 = param_1 + 0x11;
    local_148 = param_1;
    local_130 = param_3;
    do {
      FUN_140de19e0(param_1,local_158);
      uVar15 = FUN_140dd8370(local_100,local_158);
      uVar18 = FUN_140dd83b0(local_c8,param_6);
      uVar19 = FUN_140dd83f0(local_a8,param_4 + 200);
      uVar15 = FUN_140dd9df0(local_80,FUN_140de2ba0,&local_148,&local_130,uVar19,uVar18,uVar15);
      FUN_140dd8970(&local_168,uVar15);
      plVar4 = local_50;
      if (local_50 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_50 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_50)(local_50);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      plVar4 = local_60;
      if (local_60 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_60 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_60)(local_60);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      plVar4 = local_70;
      if (local_70 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_70 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_70)(local_70);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      plVar4 = local_a0;
      if (local_a0 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_a0 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_a0)(local_a0);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      plVar4 = local_c0;
      if (local_c0 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_c0 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_c0)(local_c0);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      plVar4 = local_f8;
      if (local_f8 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_f8 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_f8)(local_f8);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*plVar4 + 8))(plVar4);
          }
        }
      }
      puVar5 = (undefined4 *)param_1[0x12];
      if ((&local_168 < puVar5) && (puVar21 = (undefined4 *)*puVar3, puVar21 <= &local_168)) {
        if (puVar5 == (undefined4 *)param_1[0x13]) {
          FUN_140de7020(puVar3,1);
        }
        puVar21 = (undefined4 *)
                  (((longlong)&local_168 - (longlong)puVar21 & 0xfffffffffffffff0U) + *puVar3);
        puVar5 = (undefined4 *)param_1[0x12];
        if (puVar5 != (undefined4 *)0x0) {
          uVar9 = puVar21[1];
          uVar10 = puVar21[2];
          uVar7 = puVar21[3];
          *puVar5 = *puVar21;
          puVar5[1] = uVar9;
          puVar5[2] = uVar10;
          puVar5[3] = uVar7;
          puVar21[2] = 0;
        }
      }
      else {
        if (puVar5 == (undefined4 *)param_1[0x13]) {
          FUN_140de7020(puVar3,1);
        }
        puVar5 = (undefined4 *)param_1[0x12];
        if (puVar5 != (undefined4 *)0x0) {
          *puVar5 = local_168;
          puVar5[1] = uStack_164;
          puVar5[2] = iStack_160;
          puVar5[3] = uStack_15c;
          iStack_160 = 0;
        }
      }
      plVar4 = local_150;
      param_1[0x12] = param_1[0x12] + 0x10;
      if (iStack_160 != 0) {
                    /* WARNING: Subroutine does not return */
        terminate();
      }
      if (local_150 != (longlong *)0x0) {
        LOCK();
        plVar1 = local_150 + 1;
        *(int *)plVar1 = (int)*plVar1 + -1;
        UNLOCK();
        if ((int)*plVar1 == 0) {
          (**(code **)*local_150)(local_150);
          LOCK();
          piVar2 = (int *)((longlong)plVar4 + 0xc);
          *piVar2 = *piVar2 + -1;
          UNLOCK();
          if (*piVar2 == 0) {
            (**(code **)(*local_150 + 8))();
          }
        }
      }
      uVar23 = uVar23 + 1;
    } while (uVar23 < uVar12);
  }
  FUN_140de2250(param_1);
  lVar22 = 0;
  if (uVar12 != 0) {
    uVar24 = (ulonglong)uVar12;
    do {
      lVar6 = param_1[0x11];
      if (*(int *)(lVar22 + 8 + lVar6) == 0) {
                    /* WARNING: Subroutine does not return */
        FUN_14122327c(1);
      }
      puVar20 = (undefined8 *)_Thrd_current(local_90);
      local_e8 = *puVar20;
      uStack_e0 = puVar20[1];
      puVar5 = (undefined4 *)(lVar22 + lVar6);
      local_d8 = *puVar5;
      uStack_d4 = puVar5[1];
      uStack_d0 = puVar5[2];
      uStack_cc = puVar5[3];
      iVar13 = FUN_141224ab8(&local_d8,&local_e8);
      if (iVar13 != 0) {
                    /* WARNING: Subroutine does not return */
        FUN_14122327c(5);
      }
      puVar5 = (undefined4 *)(lVar22 + lVar6);
      local_b8 = *puVar5;
      uStack_b4 = puVar5[1];
      uStack_b0 = puVar5[2];
      uStack_ac = puVar5[3];
      iVar13 = _Thrd_join(&local_b8,0);
      if (iVar13 != 0) {
                    /* WARNING: Subroutine does not return */
        FUN_14122327c(2);
      }
      *(undefined4 *)(lVar22 + 8 + lVar6) = 0;
      lVar22 = lVar22 + 0x10;
      uVar24 = uVar24 - 1;
    } while (uVar24 != 0);
  }
  puVar20 = local_res10;
  *local_res10 = 0;
  local_res10[1] = 0;
  lVar22 = param_1[8];
  uVar15 = param_1[7];
  if (lVar22 != 0) {
    LOCK();
    *(int *)(lVar22 + 8) = *(int *)(lVar22 + 8) + 1;
    UNLOCK();
  }
  plVar4 = (longlong *)local_res10[1];
  if (plVar4 != (longlong *)0x0) {
    LOCK();
    plVar1 = plVar4 + 1;
    *(int *)plVar1 = (int)*plVar1 + -1;
    UNLOCK();
    if ((int)*plVar1 == 0) {
      (**(code **)*plVar4)(plVar4);
      LOCK();
      piVar2 = (int *)((longlong)plVar4 + 0xc);
      *piVar2 = *piVar2 + -1;
      UNLOCK();
      if (*piVar2 == 0) {
        (**(code **)(*plVar4 + 8))(plVar4);
      }
    }
  }
  puVar20[1] = lVar22;
  *puVar20 = uVar15;
  plVar4 = *(longlong **)(param_6 + 8);
  if (plVar4 != (longlong *)0x0) {
    LOCK();
    plVar1 = plVar4 + 1;
    *(int *)plVar1 = (int)*plVar1 + -1;
    UNLOCK();
    if ((int)*plVar1 == 0) {
      (**(code **)*plVar4)(plVar4);
      LOCK();
      piVar2 = (int *)((longlong)plVar4 + 0xc);
      *piVar2 = *piVar2 + -1;
      UNLOCK();
      if (*piVar2 == 0) {
        (**(code **)(*plVar4 + 8))(plVar4);
      }
    }
  }
  return puVar20;
}


