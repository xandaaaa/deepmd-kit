# SPDX-License-Identifier: LGPL-3.0-or-later
import copy
import unittest

import torch

from deepmd.pt.model.model import (
    get_model,
)
from deepmd.pt.utils import (
    env,
)

from ...seed import (
    GLOBAL_SEED,
)
from ..common import (
    eval_model,
)
from .test_permutation import (  # model_dpau,
    model_dos,
    model_dpa1,
    model_dpa2,
    model_dpa3,
    model_hybrid,
    model_se_e2_a,
    model_spin,
    model_zbl,
)

dtype = torch.float64


class SmoothTest:
    def test(
        self,
    ) -> None:
        generator = torch.Generator(device=env.DEVICE).manual_seed(GLOBAL_SEED)
        # displacement of atoms
        epsilon = 1e-5 if self.epsilon is None else self.epsilon
        # required prec. relative prec is not checked.
        rprec = 0
        aprec = 1e-5 if self.aprec is None else self.aprec

        natoms = 10
        cell = 8.6 * torch.eye(3, dtype=dtype, device=env.DEVICE)
        atype0 = torch.arange(3, dtype=dtype, device=env.DEVICE)
        atype1 = torch.randint(
            0, 3, [natoms - 3], device=env.DEVICE, generator=generator
        )
        atype = torch.cat([atype0, atype1]).view([natoms])
        coord0 = torch.tensor(
            [
                0.0,
                0.0,
                0.0,
                4.0 - 0.5 * epsilon,
                0.0,
                0.0,
                0.0,
                4.0 - 0.5 * epsilon,
                0.0,
                6.0 - 0.5 * epsilon,
                0.0,
                0.0,
                0.0,
                6.0 - 0.5 * epsilon,
                0.0,
            ],
            dtype=dtype,
            device=env.DEVICE,
        ).view([-1, 3])  # to test descriptors with two rcuts, e.g. DPA2/3
        coord1 = torch.rand(
            [natoms - coord0.shape[0], 3],
            dtype=dtype,
            device=env.DEVICE,
            generator=generator,
        )
        coord1 = torch.matmul(coord1, cell)
        coord = torch.concat([coord0, coord1], dim=0)
        spin = torch.rand(
            [natoms, 3], dtype=dtype, device=env.DEVICE, generator=generator
        )
        coord0 = torch.clone(coord)
        coord1 = torch.clone(coord)
        coord1[1][0] += epsilon
        coord1[3][0] += epsilon
        coord2 = torch.clone(coord)
        coord2[2][1] += epsilon
        coord2[4][1] += epsilon
        coord3 = torch.clone(coord)
        coord3[1][0] += epsilon
        coord1[3][0] += epsilon
        coord3[2][1] += epsilon
        coord2[4][1] += epsilon
        test_spin = getattr(self, "test_spin", False)
        if not test_spin:
            test_keys = ["energy", "force", "virial"]
        else:
            test_keys = ["energy", "force", "force_mag", "virial"]

        result_0 = eval_model(
            self.model,
            coord0.unsqueeze(0),
            cell.unsqueeze(0),
            atype,
            spins=spin.unsqueeze(0),
        )
        ret0 = {key: result_0[key].squeeze(0) for key in test_keys}
        result_1 = eval_model(
            self.model,
            coord1.unsqueeze(0),
            cell.unsqueeze(0),
            atype,
            spins=spin.unsqueeze(0),
        )
        ret1 = {key: result_1[key].squeeze(0) for key in test_keys}
        result_2 = eval_model(
            self.model,
            coord2.unsqueeze(0),
            cell.unsqueeze(0),
            atype,
            spins=spin.unsqueeze(0),
        )
        ret2 = {key: result_2[key].squeeze(0) for key in test_keys}
        result_3 = eval_model(
            self.model,
            coord3.unsqueeze(0),
            cell.unsqueeze(0),
            atype,
            spins=spin.unsqueeze(0),
        )
        ret3 = {key: result_3[key].squeeze(0) for key in test_keys}

        def compare(ret0, ret1) -> None:
            for key in test_keys:
                if key in ["energy"]:
                    torch.testing.assert_close(
                        ret0[key], ret1[key], rtol=rprec, atol=aprec
                    )
                elif key in ["force", "force_mag"]:
                    # plus 1. to avoid the divided-by-zero issue
                    torch.testing.assert_close(
                        1.0 + ret0[key], 1.0 + ret1[key], rtol=rprec, atol=aprec
                    )
                elif key == "virial":
                    if not hasattr(self, "test_virial") or self.test_virial:
                        torch.testing.assert_close(
                            1.0 + ret0[key], 1.0 + ret1[key], rtol=rprec, atol=aprec
                        )
                else:
                    raise RuntimeError(f"Unexpected test key {key}")

        compare(ret0, ret1)
        compare(ret1, ret2)
        compare(ret0, ret3)


class TestEnergyModelSeA(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_se_e2_a)
        self.type_split = False
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


class TestDOSModelSeA(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dos)
        self.type_split = False
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


class TestEnergyModelDPA1(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa1)
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        # less degree of smoothness,
        # error can be systematically removed by reducing epsilon
        self.epsilon = 1e-5
        self.aprec = 1e-5


class TestEnergyModelDPA1Excl1(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa1)
        model_params["pair_exclude_types"] = [[0, 1]]
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        # less degree of smoothness,
        # error can be systematically removed by reducing epsilon
        self.epsilon = 1e-5
        self.aprec = 1e-5


class TestEnergyModelDPA1Excl12(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa1)
        model_params["pair_exclude_types"] = [[0, 1], [0, 2]]
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        # less degree of smoothness,
        # error can be systematically removed by reducing epsilon
        self.epsilon = 1e-5
        self.aprec = 1e-5


class TestEnergyModelDPA2(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa2)
        model_params["descriptor"]["repinit"]["rcut"] = 8
        model_params["descriptor"]["repinit"]["rcut_smth"] = 3.5
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = 1e-5, 1e-4


class TestEnergyModelDPA2_1(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa2)
        model_params["fitting_net"]["type"] = "ener"
        self.type_split = True
        self.test_virial = False
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


class TestEnergyModelDPA2_2(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa2)
        model_params["fitting_net"]["type"] = "ener"
        self.type_split = True
        self.test_virial = False
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


class TestEnergyModelDPA3(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_dpa3)
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        # less degree of smoothness,
        # error can be systematically removed by reducing epsilon
        self.epsilon = 1e-5
        self.aprec = 1e-5


class TestEnergyModelHybrid(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_hybrid)
        self.type_split = True
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


class TestEnergyModelZBL(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_zbl)
        self.type_split = False
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, 5e-2


class TestEnergyModelSpinSeA(unittest.TestCase, SmoothTest):
    def setUp(self) -> None:
        model_params = copy.deepcopy(model_spin)
        self.type_split = False
        self.test_spin = True
        self.model = get_model(model_params).to(env.DEVICE)
        self.epsilon, self.aprec = None, None


# class TestEnergyFoo(unittest.TestCase):
#   def test(self):
#     model_params = model_dpau
#     self.model = EnergyModelDPAUni(model_params).to(env.DEVICE)

#     natoms = 5
#     cell = torch.rand([3, 3], dtype=dtype)
#     cell = (cell + cell.T) + 5. * torch.eye(3)
#     coord = torch.rand([natoms, 3], dtype=dtype)
#     coord = torch.matmul(coord, cell)
#     atype = torch.IntTensor([0, 0, 0, 1, 1])
#     idx_perm = [1, 0, 4, 3, 2]
#     ret0 = infer_model(self.model, coord, cell, atype, type_split=True)


if __name__ == "__main__":
    unittest.main()
