from __future__ import absolute_import, division, print_function

import ast
import sys

import h5py

import libtbx

from dxtbx.format.FormatNexus import FormatNexus
from dxtbx.masking import GoniometerMaskerFactory
from dxtbx.model import MultiAxisGoniometer

# These are the instrument names that should be used according to
# https://manual.nexusformat.org/classes/applications/NXmx.html and
# https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_diffrn_source.type.html
VALID_NAMES = {
    # "long" names
    b"DIAMOND BEAMLINE I03",
    b"DIAMOND BEAMLINE I04",
    # "short" names
    b"DLS I03",
    b"DLS I04",
    # "legacy" names used until 2021/03/12
    b"I03",
    b"I04",
}


def get_count_limit_from_meta(meta_file_name):
    with h5py.File(meta_file_name, "r") as f:

        config = f["/config"][()]
        config_data = ast.literal_eval(config.decode("utf-8"))

    return config_data["countrate_correction_count_cutoff"]


class FormatNexusEigerDLS16M(FormatNexus):
    @staticmethod
    def understand(image_file):
        """Check to see if this format class can understand the image file.

        Args:
          image_file (str): The file path of the image file to check.

        Returns:
          bool: Returns ``True`` if the image_file is understood by this format class,
          else returns ``False``.

        """

        # this depends on DIALS for the goniometer shadow model; if missing
        # simply return False

        # Get the file handle
        with h5py.File(image_file, "r") as handle:
            name = FormatNexusEigerDLS16M.get_instrument_name(handle)
            return name and name.upper() in VALID_NAMES

    def has_dynamic_shadowing(self, **kwargs):
        dynamic_shadowing = kwargs.get("dynamic_shadowing", False)
        if not isinstance(self.get_goniometer(), MultiAxisGoniometer):
            # Single-axis goniometer, no goniometer shadows
            return False
        if dynamic_shadowing in (libtbx.Auto, "Auto"):
            return True
        return dynamic_shadowing

    def __init__(self, image_file, **kwargs):
        """Initialise the image structure from the given file."""

        super(FormatNexusEigerDLS16M, self).__init__(image_file, **kwargs)
        self._dynamic_shadowing = self.has_dynamic_shadowing(**kwargs)

    def get_detector(self, index=None):
        if not self._image_file.endswith("_master.h5"):
            return self._detector()

        # workaround for https://jira.diamond.ac.uk/browse/I03-365
        # read the count limit from the meta file - if anything goes
        # wrong, do nothing

        detector = self._detector()

        try:
            meta = self._image_file.replace("_master.h5", "_meta.h5")
            limit = get_count_limit_from_meta(meta)

            assert limit > 0

            for panel in detector:
                trusted = panel.get_trusted_range()
                panel.set_trusted_range((trusted[0], limit))
        except Exception:
            pass

        return detector

    def get_goniometer_shadow_masker(self, goniometer=None):
        if not self._dynamic_shadowing:
            return None

        if goniometer is None:
            goniometer = self.get_goniometer()

        assert goniometer is not None

        if goniometer.get_names()[1] == "chi":
            return GoniometerMaskerFactory.smargon(goniometer)
        elif goniometer.get_names()[1] == "kappa":
            return GoniometerMaskerFactory.mini_kappa(goniometer)

        else:
            raise RuntimeError(
                "Don't understand this goniometer: %s" % list(goniometer.get_names())
            )


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(FormatNexusEigerDLS16M.understand(arg))
