# -*- coding: utf-8 -*-
"""AiiDA-ORCA output parser"""
import numpy as np

from pymatgen.core import Molecule

from aiida.parsers import Parser
from aiida.common import OutputParsingError, NotExistent
from aiida.engine import ExitCode
from aiida.orm import Dict, StructureData

from .cclib.utils import PeriodicTable
from .cclib.ccio import ccread


class OrcaBaseParser(Parser):
    """Basic AiiDA parser for the output of Orca"""

    def parse(self, **kwargs):
        """
        It uses cclib to get the output dictionary.
        Herein, we report all parsed data by ccli in output_dict which
        can be parsed further at workchain level.
        If it would be an optimization run, the relaxed structure also will
        be stored under relaxed_structure key.
        """

        try:
            out_folder = self.retrieved
        except NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        fname_out = self.node.process_class._OUTPUT_FILE  #pylint: disable=protected-access
        fname_relaxed = self.node.process_class._RELAX_COORDS_FILE  #pylint: disable=protected-access
        # fname_traj = self.node.process_class._TRAJECTORY_FILE  #pylint: disable=protected-access
        # fname_hessian = self.node.process_class._HESSIAN_FILE  #pylint: disable=protected-access

        if fname_out not in out_folder._repository.list_object_names():  #pylint: disable=protected-access
            raise OutputParsingError('Orca output file not retrieved')

        try:
            with self.retrieved.open(fname_out) as handler:
                parsed_obj = ccread(handler.name)
                parsed_dict = parsed_obj.getattributes()
        except OutputParsingError:  #pylint: disable=bare-except
            return self.exit_codes.ERROR_OUTPUT_PARSING

        def _remove_nan(parsed_dictionary: dict) -> dict:
            """cclib parsed object may contain nan values in ndarray.
            It will results in an exception in aiida-core which comes from
            json serialization and thereofore dictionary cannot be stored.
            This removes nan values to remedy this issue.
            See:
            https://github.com/aiidateam/aiida-core/issues/2412
            https://github.com/aiidateam/aiida-core/issues/3450

            Args:
                parsed_dictionary (dict): Parsed dictionary from `cclib`

            Returns:
                dict: Parsed dictionary without `NaN`
            """

            for key, value in parsed_dictionary.items():
                if isinstance(value, np.ndarray):
                    non_nan_value = np.nan_to_num(value, nan=123456789, posinf=2e308, neginf=-2e308)
                    parsed_dictionary.update({key: non_nan_value})

            return parsed_dictionary

        output_dict = _remove_nan(parsed_dict)

        # keywords = output_dict['metadata']['keywords']

        if parsed_dict.get('optdone', False):
            with out_folder.open(fname_relaxed) as handler:
                relaxed_structure = StructureData(pymatgen_molecule=Molecule.from_file(handler.name))
            self.out('relaxed_structure', relaxed_structure)
            # relaxation_trajectory = SinglefileData(
            #     file=os.path.join(out_folder._repository._get_base_folder().abspath, fname_traj)  #pylint: disable=protected-access
            # )
            # self.out('relaxation_trajectory', relaxation_trajectory)

        pt = PeriodicTable()  #pylint: disable=invalid-name

        output_dict['elements'] = [pt.element[Z] for Z in output_dict['atomnos'].tolist()]

        self.out('output_parameters', Dict(dict=output_dict))

        return ExitCode(0)


#EOF
