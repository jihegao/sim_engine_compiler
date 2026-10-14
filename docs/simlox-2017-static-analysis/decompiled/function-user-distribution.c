/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-user-distribution.json
 * Evidence: ev_87379b1c0a32c6fe4ce8807de5f98e2f8c4af874cbe1b9e7f638500c7a0e44c3
 */


double FUN_140e47e30(longlong *param_1,undefined8 param_2,double param_3)

{
  uint uVar1;
  double *pdVar2;
  uint uVar3;
  double *pdVar4;
  double *pdVar5;
  double *pdVar6;
  double dVar7;
  double dVar8;
  
  pdVar2 = (double *)0x0;
  dVar8 = 0.0;
  if ((int)(param_1[6] - param_1[5] >> 3) < 2) {
    if ((param_1[6] - param_1[5] >> 3 == 0) || ((int)(param_1[6] - param_1[5] >> 3) < 1)) {
                    /* WARNING: Subroutine does not return */
      FUN_1411a8cb0(1);
    }
    pdVar6 = *(double **)param_1[5];
  }
  else {
    dVar7 = (double)FUN_140c4aa00(param_2,0,0x3ff0000000000000);
    pdVar4 = pdVar2;
    pdVar6 = pdVar2;
    if (param_1[6] - param_1[5] >> 3 != 0) {
      do {
        uVar3 = (uint)(param_1[6] - param_1[5] >> 3);
        if ((int)uVar3 <= (int)pdVar2) {
                    /* WARNING: Subroutine does not return */
          FUN_1411a8cb0(1);
        }
        uVar1 = (int)pdVar2 + 1;
        pdVar2 = (double *)(ulonglong)uVar1;
        pdVar5 = (double *)((longlong)pdVar4 + 1);
        if (uVar1 == uVar3) {
          pdVar2 = (double *)0xffffffff;
          pdVar5 = (double *)0xffffffffffffffff;
        }
        pdVar6 = *(double **)(param_1[5] + (longlong)pdVar4 * 8);
        dVar8 = dVar8 + *pdVar6;
      } while ((dVar8 <= dVar7) && (pdVar4 = pdVar5, -1 < (int)pdVar2));
    }
  }
  dVar8 = (double)(**(code **)(*(longlong *)pdVar6[4] + 0x58))
                            ((longlong *)pdVar6[4],param_2,pdVar6[1],pdVar6[2],pdVar6[3]);
  dVar7 = (double)(**(code **)(*param_1 + 0x50))(param_1);
  return (param_3 / dVar7) * dVar8;
}


