import ssl,threading,unittest,urllib.error
from unittest.mock import patch
import neptune_trainer as trainer

class ConnectionRecovery(unittest.TestCase):
    def test_heartbeat_timeout_retries_without_failing_the_run(self):
        with patch.object(trainer,'_api_once',side_effect=[TimeoutError('read timed out'),{'ok':True}]) as call,patch.object(trainer.time,'sleep'):
            self.assertEqual(trainer.api({},'page_heartbeat',{}),{'ok':True});self.assertEqual(call.call_count,2)
    def test_result_upload_reuses_exact_idempotent_payload(self):
        payload={'job_id':'job','lease':'test','result':{'model':'saved'}}
        with patch.object(trainer,'_api_once',side_effect=[ConnectionResetError(),{'ok':True}]) as call,patch.object(trainer.time,'sleep'):
            trainer.api({},'finish',payload);self.assertIs(call.call_args_list[0].args[2],call.call_args_list[1].args[2])
    def test_claim_is_not_blindly_replayed(self):
        with patch.object(trainer,'_api_once',side_effect=TimeoutError()) as call:
            with self.assertRaises(TimeoutError):trainer.api({},'page_claim',{})
            self.assertEqual(call.call_count,1)
    def test_authentication_expired_lease_and_certificates_are_not_network_retries(self):
        for error in [trainer.TrainingApiError('expired',401),trainer.TrainingApiError('revoked',403),trainer.TrainingApiError('lease',409),urllib.error.URLError(ssl.SSLCertVerificationError('invalid'))]:
            self.assertFalse(trainer.connection_error(error))
            with patch.object(trainer,'_api_once',side_effect=error) as call:
                with self.assertRaises(type(error)):trainer.api({},'page_heartbeat',{})
                self.assertEqual(call.call_count,1)
    def test_poll_timeout_never_reports_ready_and_does_not_exit(self):
        closing=threading.Event();messages=[];connections=[]
        def wait(seconds):closing.set();return True
        with patch.object(trainer,'api',side_effect=TimeoutError()),patch.object(closing,'wait',side_effect=wait):
            trainer.watch_jobs({}, {},None,messages.append,closing,threading.Event(),connection=connections.append)
        self.assertEqual(connections,[False]);self.assertTrue(any('reconnecting' in m for m in messages));self.assertFalse(any('Ready.' in m for m in messages))
    def test_connection_recovers_and_checks_same_job_before_retrying_saved_work(self):
        closing=threading.Event();messages=[];actions=[];job={'id':'same-job','lease':'same-lease'};runs=[]
        def api(config,action,payload):
            actions.append(action)
            return {'job':job} if action=='page_claim' else {'ok':True}
        def execute(config,requested,*args,**kw):
            runs.append(requested)
            if len(runs)==1:raise TimeoutError('upload timed out')
            closing.set();return {'state':'candidate'}
        with patch.object(trainer,'api',side_effect=api),patch.object(closing,'wait',return_value=False):
            trainer.watch_jobs({}, {},execute,messages.append,closing,threading.Event())
        self.assertEqual(actions,['page_claim','page_heartbeat']);self.assertEqual(runs,[job,job]);self.assertFalse(any('Ready.' in m for m in messages))
    def test_revoked_credentials_do_not_loop_forever(self):
        closing=threading.Event();errors=[]
        with patch.object(trainer,'api',side_effect=trainer.TrainingApiError('revoked',403)) as call:
            trainer.watch_jobs({}, {},None,lambda m:None,closing,threading.Event(),failed=errors.append)
        self.assertEqual(call.call_count,1);self.assertEqual(errors,['revoked'])

if __name__=='__main__':unittest.main()
