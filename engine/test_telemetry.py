import threading
import unittest
from unittest.mock import patch
import neptune_telemetry as telemetry

class DesktopTelemetry(unittest.TestCase):
    def test_display_listener_receives_snapshot_and_can_unsubscribe(self):
        seen=[];remove=telemetry.subscribe(seen.append)
        try:
            payload={'stats':{'cpu':17,'gpu':None},'busy':False};telemetry.notify(payload)
            self.assertEqual(seen,[payload]);remove();telemetry.notify(payload);self.assertEqual(len(seen),1)
        finally:remove()
    def test_display_failure_does_not_break_other_listeners(self):
        seen=[]
        def broken(payload):raise RuntimeError('display failed')
        one=telemetry.subscribe(broken);two=telemetry.subscribe(seen.append)
        try:telemetry.notify({'stats':{}});self.assertEqual(len(seen),1)
        finally:one();two()
    def test_local_readings_continue_when_site_checkin_fails(self):
        closing=threading.Event();seen=[];remove=telemetry.subscribe(seen.append)
        def send(payload):closing.set();raise OSError('site offline')
        try:
            reporter=telemetry.Reporter(send,lambda:{'busy':False},lambda reply:None,closing)
            with patch.object(telemetry,'system',return_value={'cpu':25,'gpu':None}):reporter.run()
            self.assertEqual(seen[0]['stats']['cpu'],25)
        finally:remove()
if __name__=='__main__':unittest.main()
