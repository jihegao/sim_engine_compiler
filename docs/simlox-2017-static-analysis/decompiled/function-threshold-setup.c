/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-threshold-setup.json
 * Evidence: ev_9da8a8976a5a48a3a984ee0af1da6fb65eac24364df8b87f824b7413a9c5d5ea
 */


void FUN_140deb150(longlong param_1,undefined8 param_2,undefined8 *param_3)

{
  undefined4 uVar1;
  undefined8 uVar2;
  double dVar3;
  
  uVar2 = FUN_140d39bb0(param_2);
  dVar3 = (double)FUN_140c8b3b0(uVar2);
  *(double *)(param_1 + 0x120) = dVar3;
  *(bool *)(param_1 + 0x11c) = 2.220446049250313e-16 < dVar3;
  if (2.220446049250313e-16 < dVar3) {
    (**(code **)(**(longlong **)(param_1 + 0xd0) + 0x10))
              (*(longlong **)(param_1 + 0xd0),
               "Target confidence level will be continuously evaluated.");
    *(undefined4 *)(param_1 + 0x118) = 1;
  }
  else {
    uVar2 = FUN_140d39bb0(param_2);
    uVar1 = FUN_140c8b2c0(uVar2);
    *(undefined4 *)(param_1 + 0x118) = uVar1;
  }
  FUN_140f14330(*(undefined8 *)(param_1 + 0x108),*param_3);
  return;
}


