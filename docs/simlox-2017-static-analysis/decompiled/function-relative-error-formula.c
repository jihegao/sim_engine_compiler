/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-relative-error-formula.json
 * Evidence: ev_dba2b17876fd5aa6a1210c86871a519cd3a6c57d73385d4f9e9b1aa929437a3d
 */


double FUN_140e5e590(undefined8 param_1,double param_2,double param_3,int param_4)

{
  double dVar1;
  double dVar2;
  
  dVar1 = 0.0;
  if (1 < param_4) {
    dVar2 = ((param_3 - param_2 * param_2 * (double)param_4) / (double)(param_4 + -1)) /
            (double)param_4;
    if (0.0 < dVar2) {
      dVar1 = (double)FUN_1411a648c(dVar2);
    }
  }
  if (0.0 < param_2) {
    return dVar1 / param_2;
  }
  return 0.0;
}


