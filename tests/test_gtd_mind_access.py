"""Public connector must refuse an unprotected or unhealthy origin."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'access', Path(__file__).resolve().parents[1] / 'scripts/gtd_mind_access.py')
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)


class OriginGuardTest(unittest.TestCase):
    def setUp(self):
        self.info = {
            'Config': {'Env': ['AUTH_MODE=cloudflare',
                               'APP_ORIGIN=https://gtd.purpletardis.xyz',
                               'CLOUDFLARE_OWNER_EMAIL=titocruz@gmail.com']},
            'HostConfig': {'PortBindings': {'3000/tcp': [
                {'HostIp': '127.0.0.1', 'HostPort': '3000'}]}},
            'State': {'Health': {'Status': 'healthy'}},
        }

    def test_accepts_healthy_protected_loopback_origin(self):
        access.validate_origin(self.info)

    def test_rejects_wrong_auth_origin_or_owner(self):
        for index, replacement in enumerate([
                'AUTH_MODE=local', 'APP_ORIGIN=http://127.0.0.1:3000',
                'CLOUDFLARE_OWNER_EMAIL=other@example.test']):
            with self.subTest(replacement=replacement):
                info = copy.deepcopy(self.info)
                info['Config']['Env'][index] = replacement
                with self.assertRaises(RuntimeError):
                    access.validate_origin(info)

    def test_rejects_public_bind_or_unhealthy_container(self):
        for public in (True, False):
            info = copy.deepcopy(self.info)
            if public:
                info['HostConfig']['PortBindings']['3000/tcp'][0]['HostIp'] = '0.0.0.0'
            else:
                info['State']['Health']['Status'] = 'unhealthy'
            with self.assertRaises(RuntimeError):
                access.validate_origin(info)
