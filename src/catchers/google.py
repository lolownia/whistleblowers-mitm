import re
import json
from catchers.base import *

class Gmail(Catcher):
    def __init__(self):
        hosts = [r"mail\.google\.com"]
        paths = [ r"^/mail"]
        super(Gmail, self).__init__(hosts, paths)

    json_batch_start = re.compile(r"^\s*\d+\s*\[", re.MULTILINE)

    def fix_json(self, content):
        #print ">>>%s<<<<" % content
        if not content.startswith(")]}'"):
            return None
        content = content[4:]
        if self.json_batch_start.match(content):
            print "funny google json batch"
            return None

        content = content.replace("\n","")
        # remove singlequoted  'signature' 
        content = re.sub(r"'\w+'\]$","0]", content) 
        # fill emptiness with nulls....
        content = re.sub(r",(?=,)", ",null", content)
        return content

    @catcher
    def ui_update(self, flow):
        content = flow.response.get_decoded_content()

        content = self.fix_json(content)
        if content is None: 
            return 0
        try:
            envelope = json.loads(content)
        except ValueError:
            print content
            import pdb; pdb.set_trace()
            return 0

        assert len(envelope) == 2
        data = envelope[0]
        ctr = 0
        for m in data:
            if m[0] == 'tb':
                ctr += self.parse_tb(flow, m)
            if m[0] == 'ms':
                ctr += self.parse_ms(flow, m)
        return ctr
            
    def parse_tb(self, flow, m):
        thread_list = m[2]
        ctr = 0
        for thread in thread_list:
            tid = thread[0]
            adresses = thread[7]
            subject = thread[9]
            body = thread[10]
            frm = thread[16]
            fact = {'kind': 'mail',
                    'id': tid,
                    'provider': 'google',
                    'subject': subject,
                    'frm': frm,
                    'to': None,
                    'to_name': adresses,
                    'content': body
                }
            print "THREAD", fact
            try:
                self.save(flow, fact)
            except Exception, e:
                print "CANNOT ADD THREAD %s" % e

            ctr += 1
        return ctr

    def parse_ms(self, flow, m):
        ctr = 0
        fact = {
            'kind': 'mail',
            'provider': 'google',
            'id': m[1],
            'reply': m[2] or None,
            'frm_name': m[5],
            'frm': m[6],
            'content': m[8],
            'subject': m[12]
            }
        print "MAIL", fact
        self.save(flow, fact, selector={'kind':'mail', 'id': fact['id']})

        ctr += 1        
        detail = m[13] # 
        fact['to'] = detail[1]
        fact['subject'] = detail[5]
        fact['content'] = detail[6]
        print "DETAIL", fact
        self.save(flow, fact, selector={'kind':'mail', 'id': fact['id']})
        ctr += 1

        return ctr