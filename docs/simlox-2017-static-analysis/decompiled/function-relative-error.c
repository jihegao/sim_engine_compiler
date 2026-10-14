/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-relative-error.json
 * Evidence: ev_9f5dd9ea24bde98c951dc0271ebb2d1b27d91823c0e8836f1e8c0fb2da2db1da
 */


undefined8 FUN_140c896b0(longlong param_1,undefined8 param_2)

{
  FUN_140e5eff0(*(undefined8 *)(param_1 + 0x50),param_2,
                (*(longlong **)(param_1 + 0xd8))[1] - **(longlong **)(param_1 + 0xd8) >> 3);
  return param_2;
}


