/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-rng-seed.json
 * Evidence: ev_3279160e3e1df34de9cb7619b5553597627aae217c4aa7a98f87dac5f574aae1
 */


undefined8 * FUN_140de0e40(undefined8 *param_1,uint param_2)

{
  *param_1 = CSimulationSeedHandler::vftable;
  _Mtx_destroy();
  if ((param_2 & 1) != 0) {
    free(param_1);
  }
  return param_1;
}


