"""Opt-in real Docker recovery test; synthetic data, random loopback port, no tokens."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from test_gtd_mind_upgrade import upgrade


@unittest.skipUnless(os.environ.get('GTD_UPGRADE_LIVE_TEST') == '1', 'explicit Docker rehearsal only')
class LiveUpgradeTest(unittest.TestCase):
    def test_upgrade_and_failed_verification_recovery(self):
        root = Path(tempfile.mkdtemp(prefix='gtd-upgrade-live-'))
        os.chmod(root, 0o700)
        (root / 'state').mkdir(mode=0o700)
        (root / 'config').mkdir(mode=0o700)
        config = root / 'config/gtd-mind.env'
        config.write_text('AUTH_MODE=local\nAPP_ORIGIN=http://127.0.0.1:3000\n')
        config.chmod(0o600)
        image = 'gtd-mind:edeee2ab870a'
        new_image = 'gtd-mind:e323e29a6b83'

        class Isolated(upgrade.Upgrade):
            def stop_tunnel(self):
                # This isolated test has no connector; never touch production.
                return

            def switch(self, selected):
                upgrade.run('docker', 'rm', '-f', self.container)
                upgrade.run('docker', 'run', '-d', '--name', self.container, '--read-only',
                            '--tmpfs', '/tmp', '--user', f'{os.getuid()}:{os.getgid()}',
                            '-p', '127.0.0.1::3000',
                            '-v', str(self.db.parent) + ':/data', '-e', 'AUTH_MODE=local',
                            '-e', 'APP_ORIGIN=http://127.0.0.1:3000', selected)
                port = self.inspect()['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
                self.origin = 'http://127.0.0.1:' + port

        engine = Isolated(Path('/Users/titocr/code/gtd-ai'), root)
        engine.container = 'gtd-upgrade-test-' + uuid.uuid4().hex[:12]
        # Create the first container directly; switch() only replaces existing resources.
        upgrade.run('docker', 'create', '--name', engine.container, image)
        try:
            engine.switch(image)
            upgrade.check_app(engine.origin, 'owner')
            with closing(sqlite3.connect(engine.db)) as db:
                count = db.execute('SELECT count(*) FROM work_items').fetchone()[0]
            record = dict(image=new_image, previous_image=image, actor='owner',
                          schema=upgrade.fingerprint(engine.db), sync_configured=False)
            rehearsal = root / 'rehearsal'
            rehearsal.mkdir()
            engine.rehearse(new_image, rehearsal, record)
            engine.apply(record, root / 'success.json')
            self.assertEqual(json.loads((root / 'success.json').read_text())['status'], 'succeeded')
            original = engine.verify
            engine.switch(image)
            calls = []

            def fail_once(*args, **kwargs):
                calls.append(1)
                original(*args, **kwargs)
                if len(calls) == 1:
                    raise RuntimeError('Injected post-start verification failure')

            engine.verify = fail_once
            with self.assertRaisesRegex(RuntimeError, 'Injected'):
                engine.apply(record, root / 'failure.json')
            self.assertEqual(json.loads((root / 'failure.json').read_text())['status'], 'rolled-back')
            upgrade.check_app(engine.origin, 'owner')
            with closing(sqlite3.connect(engine.db)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM work_items').fetchone()[0], count)
            print('Live success and rollback records: ' + str(root))
        finally:
            upgrade.run('docker', 'rm', '-f', engine.container)


if __name__ == '__main__':
    unittest.main()
