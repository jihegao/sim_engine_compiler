/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-sim-constructor.json
 * Evidence: ev_020c3105e7973bc8d65400d4294adfd3b43b0ce40a94d797e5c95d5e5bd85461
 */


/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */

undefined8 *
FUN_140c461c0(undefined8 *param_1,longlong param_2,undefined8 param_3,undefined8 *param_4,
             undefined4 param_5,undefined4 param_6,undefined8 param_7,undefined8 *param_8,
             undefined8 param_9,undefined8 param_10,char param_11)

{
  int *piVar1;
  uint uVar2;
  undefined8 uVar3;
  undefined8 uVar4;
  longlong *plVar5;
  longlong lVar6;
  longlong lVar7;
  longlong *plVar8;
  ulonglong *puVar9;
  longlong lVar10;
  undefined8 uVar11;
  undefined8 *puVar12;
  undefined8 *puVar13;
  undefined8 *puVar14;
  char ****ppppcVar15;
  ulonglong _Size;
  int iVar16;
  ulonglong uVar17;
  int iVar18;
  ulonglong uVar19;
  undefined8 *puVar20;
  undefined8 *puVar21;
  bool bVar22;
  undefined1 auStack_1c8 [32];
  undefined8 local_1a8;
  undefined8 *local_1a0;
  longlong *local_190;
  undefined8 *local_188;
  longlong local_180;
  undefined8 local_178;
  undefined8 *local_170;
  undefined8 *local_168;
  undefined4 local_160 [2];
  undefined8 *local_158;
  undefined8 *local_150;
  undefined8 *local_148;
  longlong *local_140;
  undefined8 local_138;
  undefined8 uStack_130;
  undefined8 local_128;
  undefined8 uStack_120;
  undefined8 local_118;
  undefined8 uStack_110;
  undefined8 local_108;
  undefined8 uStack_100;
  undefined1 local_f8 [16];
  undefined8 local_e8;
  undefined8 local_e0;
  undefined1 local_d8 [16];
  undefined8 local_c8;
  undefined8 local_c0;
  undefined1 local_b8 [16];
  undefined8 local_a8;
  undefined8 local_a0;
  undefined8 local_98;
  undefined8 *local_90;
  undefined8 *local_88;
  undefined1 local_80 [32];
  char ***local_60 [3];
  ulonglong local_48;
  ulonglong local_40;
  
  local_98 = 0xfffffffffffffffe;
  local_40 = DAT_141ce8fd0 ^ (ulonglong)auStack_1c8;
  local_148 = param_8;
  local_88 = param_8;
  *param_1 = CSimData::vftable;
  *(undefined4 *)(param_1 + 2) = param_5;
  *(undefined4 *)((longlong)param_1 + 0x14) = param_6;
  param_1[3] = param_2;
  param_1[4] = param_3;
  param_1[5] = param_4;
  param_1[6] = param_9;
  uVar4 = 0;
  param_1[7] = 0;
  param_1[8] = 0;
  uVar3 = *param_8;
  if (param_8[1] != 0) {
    LOCK();
    piVar1 = (int *)(param_8[1] + 8);
    *piVar1 = *piVar1 + 1;
    UNLOCK();
  }
  local_188 = param_1;
  local_180 = param_2;
  local_158 = param_4;
  local_90 = param_1;
  FUN_140c49e20(param_1 + 7,uVar3);
  *(undefined4 *)(param_1 + 10) = 0;
  param_1[0xb] = 0;
  param_1[0xc] = 0;
  param_1[9] = CSimStationList::vftable;
  param_1[0xd] = 0;
  param_1[0xe] = 0;
  param_1[0xf] = 0;
  param_1[0x10] = head::vftable;
  *(undefined4 *)(param_1 + 0x11) = 0;
  param_1[0x12] = 0;
  param_1[0x13] = 0;
  param_1[0x14] = head::vftable;
  *(undefined4 *)(param_1 + 0x15) = 0;
  param_1[0x16] = 0;
  param_1[0x17] = 0;
  param_1[0x1a] = head::vftable;
  *(undefined4 *)(param_1 + 0x1b) = 0;
  param_1[0x1c] = 0;
  param_1[0x1d] = 0;
  param_1[0x1e] = param_10;
  param_1[0x27] = param_7;
  local_138 = 0;
  uStack_130 = 0;
  local_128 = 0;
  uStack_120 = 0;
  local_118 = 0;
  uStack_110 = 0;
  local_108 = 0;
  uStack_100 = 0;
  param_1[0x28] = 0;
  param_1[0x29] = 0;
  param_1[0x2a] = 0;
  param_1[0x2b] = 0;
  *(undefined4 *)(param_1 + 0x2c) = 0;
  *(undefined4 *)((longlong)param_1 + 0x164) = 0;
  *(undefined4 *)(param_1 + 0x2d) = 0;
  *(undefined4 *)((longlong)param_1 + 0x16c) = 0;
  *(undefined4 *)(param_1 + 0x2e) = 0;
  *(undefined4 *)((longlong)param_1 + 0x174) = 0;
  *(undefined4 *)(param_1 + 0x2f) = 0;
  *(undefined4 *)((longlong)param_1 + 0x17c) = 0;
  param_1[0x30] = 0;
  param_1[0x31] = 0;
  uVar3 = FUN_140c49a80(param_1 + 0x30);
  param_1[0x30] = uVar3;
  param_1[0x28] = 0;
  param_1[0x29] = 0;
  param_1[0x2a] = 0;
  param_1[0x2b] = 0;
  param_1[0x2c] = 0;
  param_1[0x2d] = 0;
  param_1[0x2e] = 0;
  param_1[0x2f] = 0;
  if (param_1[0x1e] != 0) {
    FUN_140c48a90(param_1);
  }
  local_168 = operator_new(0x78);
  if (local_168 != (undefined8 *)0x0) {
    uVar4 = FUN_140d8dc50(local_168);
  }
  param_1[1] = uVar4;
  *(undefined4 *)(param_1 + 0x19) = 0;
  plVar5 = (longlong *)FUN_140d3d4d0(param_2);
  plVar8 = (longlong *)*plVar5;
  plVar5 = (longlong *)plVar5[1];
  local_190 = plVar5;
  if (plVar8 != plVar5) {
    do {
      iVar16 = 0;
      local_178 = CONCAT44(local_178._4_4_,*(int *)(*plVar8 + 0x68));
      local_170 = (undefined8 *)((ulonglong)local_170 & 0xffffffff00000000);
      if (0 < *(int *)(*plVar8 + 0x68)) {
        do {
          lVar6 = 0;
          local_168 = operator_new(0x168);
          if (local_168 != (undefined8 *)0x0) {
            lVar6 = FUN_140d92660(local_168,param_1,*plVar8,iVar16);
          }
          FUN_140dd61d0(lVar6,param_1 + 9);
          plVar5 = (longlong *)FUN_140d39b00(param_2);
          puVar12 = (undefined8 *)*plVar5;
          puVar20 = (undefined8 *)plVar5[1];
          if (puVar12 != puVar20) {
            do {
              lVar7 = FUN_140c3de20(*puVar12);
              lVar10 = *plVar8;
              puVar14 = (undefined8 *)(lVar10 + 0x38);
              puVar13 = (undefined8 *)(lVar7 + 0x38);
              uVar19 = *(ulonglong *)(lVar7 + 0x48);
              if (0xf < *(ulonglong *)(lVar7 + 0x50)) {
                puVar13 = (undefined8 *)*puVar13;
              }
              uVar17 = *(ulonglong *)(lVar10 + 0x48);
              if (0xf < *(ulonglong *)(lVar10 + 0x50)) {
                puVar14 = (undefined8 *)*puVar14;
              }
              _Size = uVar19;
              if (uVar17 < uVar19) {
                _Size = uVar17;
              }
              if (_Size == 0) {
                uVar2 = 0;
              }
              else {
                uVar2 = memcmp(puVar14,puVar13,_Size);
              }
              if (uVar2 == 0) {
                if (uVar17 < uVar19) {
                  uVar2 = 0xffffffff;
                }
                else {
                  uVar2 = (uint)(uVar17 != uVar19);
                }
              }
              if (uVar2 == 0) {
                local_168 = operator_new(0x110);
                if (local_168 == (undefined8 *)0x0) {
                  uVar3 = 0;
                }
                else {
                  uVar3 = FUN_140e231c0(local_168,param_1,*puVar12,lVar6);
                }
                FUN_140dd61d0(uVar3,lVar6 + 0x60);
                FUN_140e27850(uVar3);
              }
              puVar12 = puVar12 + 1;
            } while (puVar12 != puVar20);
            iVar16 = (int)local_170;
          }
          plVar5 = (longlong *)FUN_140e06000(*plVar8);
          puVar13 = local_158;
          puVar12 = (undefined8 *)*plVar5;
          puVar20 = (undefined8 *)plVar5[1];
          if (puVar12 != puVar20) {
            local_168 = (undefined8 *)local_f8;
            do {
              uVar3 = FUN_140c44510(*puVar12);
              FUN_140c44350(uVar3,local_60);
              local_e0 = 0xf;
              local_e8 = 0;
              local_f8[0] = 0;
              thunk_FUN_140318fe0(local_f8,*plVar8 + 0x38,0,0xffffffffffffffff);
              ppppcVar15 = local_60;
              if (0xf < local_48) {
                ppppcVar15 = (char ****)local_60[0];
              }
              local_a0 = 0xf;
              lVar10 = 0;
              local_a8 = 0;
              local_b8[0] = 0;
              if (*(char *)ppppcVar15 != '\0') {
                lVar10 = -1;
                do {
                  lVar10 = lVar10 + 1;
                } while (*(char *)((longlong)ppppcVar15 + lVar10) != '\0');
              }
              thunk_FUN_140319190(local_b8,ppppcVar15,lVar10);
              uVar3 = FUN_140c891d0(puVar13,local_b8,local_f8);
              local_150 = operator_new(0x208);
              if (local_150 == (void *)0x0) {
                uVar3 = 0;
              }
              else {
                local_1a8 = uVar3;
                uVar3 = FUN_140d92320(local_150,param_1,lVar6,*puVar12);
              }
              local_c0 = 0xf;
              local_c8 = 0;
              local_d8[0] = 0;
              thunk_FUN_140318fe0(local_d8,local_60,0,0xffffffffffffffff);
              FUN_140d94a70(lVar6,local_d8);
              FUN_140d97760(uVar3);
              if (0xf < local_48) {
                free(local_60[0]);
              }
              puVar12 = puVar12 + 1;
            } while (puVar12 != puVar20);
            iVar16 = (int)local_170;
          }
          iVar16 = iVar16 + 1;
          local_170 = (undefined8 *)CONCAT44(local_170._4_4_,iVar16);
          plVar5 = local_190;
          param_2 = local_180;
        } while (iVar16 < (int)local_178);
      }
      plVar8 = plVar8 + 1;
    } while (plVar8 != plVar5);
  }
  plVar8 = (longlong *)FUN_140d3ae20(param_2);
  puVar12 = (undefined8 *)*plVar8;
  plVar8 = (longlong *)plVar8[1];
  local_190 = plVar8;
  if (puVar12 != plVar8) {
    do {
      iVar16 = FUN_140c3de30(*puVar12);
      iVar18 = 0;
      if (0 < iVar16) {
        do {
          local_150 = operator_new(0xc0);
          uVar3 = 0;
          if (local_150 != (void *)0x0) {
            uVar3 = FUN_140e23020(local_150,param_1,*puVar12,iVar18);
          }
          FUN_140dd61d0(uVar3,param_1 + 0x14);
          FUN_140e27230(uVar3);
          FUN_140d8e050(uVar3,1,0);
          iVar18 = iVar18 + 1;
          plVar8 = local_190;
        } while (iVar18 < iVar16);
      }
      puVar12 = puVar12 + 1;
      param_2 = local_180;
    } while (puVar12 != plVar8);
  }
  plVar5 = (longlong *)FUN_140d3d4d0();
  plVar8 = (longlong *)plVar5[1];
  plVar5 = (longlong *)*plVar5;
  local_190 = plVar8;
  if (plVar5 != plVar8) {
    do {
      puVar12 = local_188;
      iVar16 = 0;
      local_178 = CONCAT44(local_178._4_4_,*(int *)(*plVar5 + 0x68));
      if (0 < *(int *)(*plVar5 + 0x68)) {
        do {
          lVar6 = puVar12[0xb];
          lVar10 = 0;
          if (lVar6 != 0) {
            do {
              if ((*(longlong *)(lVar6 + 0x28) == *plVar5) &&
                 (lVar10 = lVar6, *(int *)(lVar6 + 0x30) == iVar16)) break;
              lVar6 = *(longlong *)(lVar6 + 0x10);
              lVar10 = 0;
            } while (lVar6 != 0);
          }
          puVar9 = (ulonglong *)FUN_140e06000();
          puVar20 = (undefined8 *)*puVar9;
          uVar17 = 0;
          uVar19 = (ulonglong)((longlong)puVar9[1] + (7 - (longlong)puVar20)) >> 3;
          if ((undefined8 *)puVar9[1] < puVar20) {
            uVar19 = uVar17;
          }
          if (uVar19 != 0) {
            do {
              uVar3 = FUN_140c44510(*puVar20);
              uVar3 = FUN_140c44350(uVar3,local_80);
              FUN_140d972f0(lVar10,uVar3);
              FUN_140d95840();
              puVar20 = puVar20 + 1;
              uVar17 = uVar17 + 1;
            } while (uVar17 != uVar19);
          }
          iVar16 = iVar16 + 1;
          plVar8 = local_190;
        } while (iVar16 < (int)local_178);
      }
      plVar5 = plVar5 + 1;
      param_1 = local_188;
      param_2 = local_180;
    } while (plVar5 != plVar8);
  }
  FUN_140d39ba0(param_2,&local_140);
  puVar12 = (undefined8 *)*local_140;
  plVar8 = (longlong *)local_140[1];
  lVar6 = local_180;
  local_190 = plVar8;
  local_168 = puVar12;
  local_150 = plVar8;
  if (puVar12 != plVar8) {
    do {
      uVar3 = *puVar12;
      iVar16 = FUN_140d3b170(lVar6,uVar3);
      if (iVar16 != 0) {
        do {
          iVar16 = iVar16 + -1;
          local_168 = operator_new(0x368);
          lVar6 = 0;
          if (local_168 != (undefined8 *)0x0) {
            lVar6 = FUN_140c4ced0(local_168,param_1,uVar3);
          }
          FUN_140dcc7c0(lVar6 + 0x40);
          FUN_140dd61d0(lVar6,param_1 + 0x1a);
          plVar8 = local_190;
          lVar6 = local_180;
        } while (iVar16 != 0);
      }
      puVar12 = puVar12 + 1;
    } while (puVar12 != plVar8);
  }
  local_168 = puVar12;
  for (lVar6 = param_1[0xb]; lVar6 != 0; lVar6 = *(longlong *)(lVar6 + 0x10)) {
    for (lVar10 = *(longlong *)(lVar6 + 0x70); lVar10 != 0; lVar10 = *(longlong *)(lVar10 + 0x10)) {
      puVar20 = (undefined8 *)0x0;
      puVar9 = (ulonglong *)FUN_140c3e280(*(undefined8 *)(lVar10 + 0x28));
      puVar12 = (undefined8 *)*puVar9;
      plVar8 = (undefined8 *)((ulonglong)((longlong)puVar9[1] + (7 - (longlong)puVar12)) >> 3);
      if ((undefined8 *)puVar9[1] < puVar12) {
        plVar8 = puVar20;
      }
      local_190 = plVar8;
      if (plVar8 != (undefined8 *)0x0) {
        do {
          lVar7 = FUN_140c3bbc0(*puVar12);
          uVar3 = *(undefined8 *)(lVar7 + 0x260);
          local_160[0] = 0;
          lVar7 = FUN_140c1f060(uVar3,local_160);
          puVar13 = local_188;
          while (lVar7 != 0) {
            uVar4 = FUN_140d39730(puVar13[3],*(undefined8 *)(lVar6 + 0x28),lVar7);
            plVar8 = (longlong *)FUN_140d96650(lVar6,uVar4);
            FUN_140e31040(plVar8);
            (**(code **)(*plVar8 + 8))(plVar8);
            (**(code **)(*plVar8 + 0x10))(plVar8);
            (**(code **)(*plVar8 + 0x18))(plVar8);
            lVar7 = FUN_140c1ff40(uVar3,local_160);
            plVar8 = local_190;
          }
          puVar12 = puVar12 + 1;
          puVar20 = (undefined8 *)((longlong)puVar20 + 1);
        } while (puVar20 != plVar8);
      }
    }
    param_1 = local_188;
  }
  local_180 = param_1[0xb];
  do {
    if (local_180 == 0) {
      local_180 = 0;
      for (lVar6 = param_1[0xb]; lVar6 != 0; lVar6 = *(longlong *)(lVar6 + 0x10)) {
        FUN_140d97800(lVar6);
      }
      for (lVar6 = param_1[0x16]; lVar6 != 0; lVar6 = *(longlong *)(lVar6 + 0x10)) {
        FUN_140e26fb0(lVar6);
      }
      for (lVar6 = param_1[0xb]; lVar6 != 0; lVar6 = *(longlong *)(lVar6 + 0x10)) {
        FUN_140d95750(lVar6);
      }
      puVar12 = operator_new(0x50);
      if (puVar12 == (undefined8 *)0x0) {
        puVar20 = (undefined8 *)0x0;
        local_190 = puVar12;
      }
      else {
        local_190 = puVar12;
        FUN_140d8dba0(puVar12,param_1[1]);
        *puVar12 = CSimDay::vftable;
        puVar12[8] = param_1;
        puVar12[9] = FUN_140c48c60;
        puVar20 = puVar12;
      }
      puVar12 = (undefined8 *)0x0;
      FUN_140c48c60(puVar20);
      puVar13 = operator_new(0x60);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CDataChangeManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 9) = 0;
        puVar13[0xb] = 0;
        puVar13[10] = FUN_140c493e0;
        puVar20 = puVar13;
      }
      param_1[0x1f] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      local_190 = operator_new(0x20);
      puVar20 = puVar12;
      if (local_190 != (void *)0x0) {
        puVar20 = (undefined8 *)FUN_140c720b0(local_190,param_1);
      }
      param_1[0x20] = puVar20;
      puVar13 = operator_new(0x70);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CResultIntervalManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 0xd) = 0;
        puVar13[10] = 0;
        puVar13[0xc] = 0;
        *(undefined4 *)(puVar13 + 0xb) = 0;
        uVar3 = FUN_140d3d1b0(*(undefined8 *)(puVar13[8] + 0x18));
        uVar3 = FUN_140e44180(uVar3);
        puVar13[10] = uVar3;
        puVar13[9] = FUN_140c49440;
        puVar20 = puVar13;
      }
      param_1[0x21] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      puVar13 = operator_new(0x70);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CResultIntervalManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 0xd) = 1;
        puVar13[10] = 0;
        puVar13[0xc] = 0;
        *(undefined4 *)(puVar13 + 0xb) = 0;
        uVar3 = FUN_140d3d1b0(*(undefined8 *)(puVar13[8] + 0x18));
        uVar3 = FUN_140e441b0(uVar3);
        puVar13[10] = uVar3;
        puVar13[9] = FUN_140c49440;
        puVar20 = puVar13;
      }
      param_1[0x22] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      puVar13 = operator_new(0x70);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CResultIntervalManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 0xd) = 2;
        puVar13[10] = 0;
        puVar13[0xc] = 0;
        *(undefined4 *)(puVar13 + 0xb) = 0;
        uVar3 = FUN_140d3d1b0(*(undefined8 *)(puVar13[8] + 0x18));
        uVar3 = FUN_140e44140(uVar3);
        puVar13[10] = uVar3;
        puVar13[9] = FUN_140c49440;
        puVar20 = puVar13;
      }
      param_1[0x23] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      puVar13 = operator_new(0x70);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CResultIntervalManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 0xd) = 3;
        puVar13[10] = 0;
        puVar13[0xc] = 0;
        *(undefined4 *)(puVar13 + 0xb) = 0;
        uVar3 = FUN_140d3d1b0(*(undefined8 *)(puVar13[8] + 0x18));
        uVar3 = FUN_140e43fb0(uVar3);
        puVar13[10] = uVar3;
        puVar13[9] = FUN_140c49440;
        puVar20 = puVar13;
      }
      param_1[0x24] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      puVar13 = operator_new(0x70);
      puVar20 = puVar12;
      local_190 = puVar13;
      if (puVar13 != (undefined8 *)0x0) {
        FUN_140d8dba0(puVar13,param_1[1]);
        *puVar13 = CResultIntervalManager::vftable;
        puVar13[8] = param_1;
        *(undefined4 *)(puVar13 + 0xd) = 4;
        puVar13[10] = 0;
        puVar13[0xc] = 0;
        *(undefined4 *)(puVar13 + 0xb) = 0;
        uVar3 = FUN_140d3d1b0(*(undefined8 *)(puVar13[8] + 0x18));
        uVar3 = FUN_140e44100(uVar3);
        puVar13[10] = uVar3;
        puVar13[9] = FUN_140c49440;
        puVar20 = puVar13;
      }
      param_1[0x25] = puVar20;
      FUN_140d8e050(puVar20,1,0);
      param_1[0x26] = 0;
      if (param_11 != '\0') {
        puVar20 = operator_new(0x68);
        local_190 = puVar20;
        if (puVar20 != (undefined8 *)0x0) {
          FUN_140d8dba0(puVar20,param_1[1]);
          *puVar20 = CSnapShotResultManager::vftable;
          puVar20[8] = param_1;
          puVar20[0xb] = 0;
          *(undefined4 *)(puVar20 + 9) = 0xffffffff;
          puVar20[10] = FUN_140c494e0;
          puVar12 = puVar20;
        }
        param_1[0x26] = puVar12;
        FUN_140d8e050(puVar12,1,0);
      }
      plVar8 = (longlong *)local_148[1];
      if (plVar8 != (longlong *)0x0) {
        LOCK();
        plVar5 = plVar8 + 1;
        *(int *)plVar5 = (int)*plVar5 + -1;
        UNLOCK();
        if ((int)*plVar5 == 0) {
          (**(code **)*plVar8)(plVar8);
          LOCK();
          piVar1 = (int *)((longlong)plVar8 + 0xc);
          *piVar1 = *piVar1 + -1;
          UNLOCK();
          if (*piVar1 == 0) {
            (**(code **)(*plVar8 + 8))(plVar8);
          }
        }
      }
      return param_1;
    }
    puVar12 = *(undefined8 **)(*(longlong *)(local_180 + 0x28) + 0x268);
    puVar20 = *(undefined8 **)(*(longlong *)(local_180 + 0x28) + 0x270);
    local_170 = puVar12;
    local_158 = puVar20;
    if (puVar12 != puVar20) {
      do {
        lVar6 = local_180;
        uVar3 = *puVar12;
        local_178 = uVar3;
        local_170 = puVar12;
        lVar10 = FUN_140e20ca0(uVar3);
        if (lVar10 != 0) {
          for (lVar7 = param_1[0xb]; lVar7 != 0; lVar7 = *(longlong *)(lVar7 + 0x10)) {
            if ((*(longlong *)(lVar7 + 0x28) == lVar10) &&
               (*(int *)(lVar7 + 0x30) == *(int *)(lVar6 + 0x30))) goto LAB_140c46ad2;
          }
          lVar7 = 0;
LAB_140c46ad2:
          uVar4 = param_1[3];
          uVar11 = FUN_140e20c40(uVar3);
          uVar4 = FUN_140d39730(uVar4,lVar10,uVar11);
          lVar6 = FUN_140e47120(uVar4);
          uVar11 = FUN_140e471b0(uVar4);
          uVar11 = FUN_140c1f550(uVar11);
          puVar13 = local_188;
          local_190 = (longlong *)FUN_140c891a0(local_188[5],uVar11,lVar6 + 0x38);
          iVar18 = 0;
          plVar8 = (longlong *)FUN_140e20c40(uVar3);
          iVar16 = (**(code **)(*plVar8 + 0x68))(plVar8);
          lVar6 = local_180;
          param_1 = local_188;
          if (0 < iVar16) {
            bVar22 = false;
            plVar8 = local_190;
            do {
              if (iVar18 == 0) {
                lVar6 = FUN_140d96510(lVar7,uVar4,0);
                bVar22 = lVar6 != 0;
                if (!bVar22) {
                  FUN_140e47120(uVar4);
                  uVar3 = FUN_140e471b0(uVar4);
                  uVar3 = FUN_140c1f550(uVar3);
                  puVar13 = local_188;
                  plVar8 = (longlong *)FUN_140c891a0(local_188[5],uVar3);
                }
LAB_140c46bbd:
                uVar3 = local_178;
                if (lVar6 == 0) goto LAB_140c46bc7;
              }
              else {
                if (bVar22) {
                  lVar6 = FUN_140d96510(lVar7,uVar4,iVar18);
                  goto LAB_140c46bbd;
                }
LAB_140c46bc7:
                local_190 = operator_new(0x178);
                plVar5 = (longlong *)0x0;
                if (local_190 != (undefined8 *)0x0) {
                  local_1a8 = CONCAT44(local_1a8._4_4_,iVar18);
                  local_1a0 = plVar8;
                  plVar5 = (longlong *)FUN_140e2e340(local_190,puVar13,lVar7,uVar4);
                }
                FUN_140e31040(plVar5);
                (**(code **)(*plVar5 + 8))(plVar5);
                (**(code **)(*plVar5 + 0x10))(plVar5);
                (**(code **)(*plVar5 + 0x18))(plVar5);
                FUN_140e34bf0(plVar5);
              }
              iVar18 = iVar18 + 1;
              plVar5 = (longlong *)FUN_140e20c40(uVar3);
              iVar16 = (**(code **)(*plVar5 + 0x68))(plVar5);
              puVar12 = local_170;
              puVar13 = local_188;
              lVar6 = local_180;
              puVar20 = local_158;
              param_1 = local_188;
            } while (iVar18 < iVar16);
          }
        }
        lVar10 = FUN_140e20c70(uVar3);
        if (lVar10 != 0) {
          for (lVar7 = param_1[0xb]; lVar7 != 0; lVar7 = *(longlong *)(lVar7 + 0x10)) {
            if ((*(longlong *)(lVar7 + 0x28) == lVar10) &&
               (*(int *)(lVar7 + 0x30) == *(int *)(lVar6 + 0x30))) goto LAB_140c46c9a;
          }
          lVar7 = 0;
LAB_140c46c9a:
          uVar4 = param_1[3];
          uVar3 = FUN_140e20c40(uVar3);
          uVar3 = FUN_140d39730(uVar4,lVar10,uVar3);
          puVar14 = (undefined8 *)0x0;
          plVar8 = (longlong *)FUN_140e20c40(local_178);
          iVar16 = (**(code **)(*plVar8 + 0x68))(plVar8);
          puVar13 = local_188;
          if (0 < iVar16) {
            bVar22 = false;
            puVar21 = puVar14;
            do {
              iVar16 = (int)puVar21;
              if (iVar16 == 0) {
                lVar6 = FUN_140d96510(lVar7,uVar3,0);
                bVar22 = lVar6 != 0;
LAB_140c46d12:
                if (lVar6 == 0) goto LAB_140c46d1b;
              }
              else {
                if (bVar22) {
                  lVar6 = FUN_140d96510(lVar7,uVar3,puVar21);
                  goto LAB_140c46d12;
                }
LAB_140c46d1b:
                if (puVar14 == (undefined8 *)0x0) {
                  FUN_140e47120(uVar3);
                  uVar4 = FUN_140e471b0(uVar3);
                  uVar4 = FUN_140c1f550(uVar4);
                  puVar14 = (undefined8 *)FUN_140c891a0(puVar13[5],uVar4);
                }
                plVar8 = (longlong *)0x0;
                local_190 = operator_new(0x178);
                if (local_190 != (undefined8 *)0x0) {
                  local_1a8 = CONCAT44(local_1a8._4_4_,iVar16);
                  local_1a0 = puVar14;
                  plVar8 = (longlong *)FUN_140e2e340(local_190,puVar13,lVar7,uVar3);
                }
                FUN_140e31040(plVar8);
                (**(code **)(*plVar8 + 8))(plVar8);
                (**(code **)(*plVar8 + 0x10))(plVar8);
                (**(code **)(*plVar8 + 0x18))(plVar8);
                FUN_140e34bf0(plVar8);
              }
              puVar21 = (undefined8 *)(ulonglong)(iVar16 + 1U);
              plVar8 = (longlong *)FUN_140e20c40(local_178);
              iVar18 = (**(code **)(*plVar8 + 0x68))(plVar8);
              puVar12 = local_170;
              puVar20 = local_158;
            } while ((int)(iVar16 + 1U) < iVar18);
          }
        }
        puVar12 = puVar12 + 1;
        param_1 = local_188;
        local_170 = puVar12;
      } while (puVar12 != puVar20);
    }
    local_180 = *(longlong *)(local_180 + 0x10);
  } while( true );
}


