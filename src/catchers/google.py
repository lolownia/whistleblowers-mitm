import re
import json
from catchers.base import *
from lxml import etree
from lxml.etree import HTMLParser


class Cahoots(Catcher):
    def __init__(self):
        hosts = [r"mail\.cahoots\.pl"]
        paths = None

        super(Cahoots, self).__init__(hosts)

    @catcher
    def mail_cahoots(self, flow):

        q = flow.request
        if q.method != "POST": return 0

        print q.get_decoded_content()
        try:
            data = PostData(q)
        except ValueError:
            return 0

        mcontent = data.val("_message")
        if not mcontent: return 0
        mto = data.val("_to")
        msubject = data.val("_subject")
        fact = {
            'kind': 'mail',
            'provider': 'cahoots',
            'subject': msubject,
            'to': [mto],
            'content': mcontent
        }
        self.save(flow, fact)
        return 1

    @catcher
    def mail_open(self, flow):

        q = flow.request
        if q.method != 'GET': return 0

        params = dict(q.get_query())
        print params
        try:
            if params['_task'][0]!='mail' or params['_action'][0]!='show': return 0
        except KeyError:
            return 0
        except IndexError:
            return 0


        content = flow.response.get_decoded_content()

        parser = HTMLParser()
        email = etree.fromstring(content, parser)
        subject = email.find(".//h2[@class='subject']")
        frm = email.find(".//td[@class='header from']//a")
        rcpt = email.findall(".//td[@class='header to']//a[@class='rcmContactAddress']")
        body = email.find(".//div[@id='messagebody']")

        fact = {'kind': 'mail',
                #'id': str(q.timestamp_start),
                'provider': 'cahoots',
                'subject': subject.text,
                'frm': frm.attrib['title'],
                'frm_name': frm.text,
                'to': [t.attrib['title'] for t in rcpt],
                'to_name': [t.text for t in rcpt],
                'content': etree.tostring(body),
                'src': 'tb'
            }

        self.save(flow, fact)
        return 1


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
            #import pdb; pdb.set_trace()
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
                    'content': body,
                    'src': 'tb'
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
            'subject': m[12],
            'src': 'ms'

            }
        print "MAIL", fact
        self.save(flow, fact, selector={'kind':'mail', 'id': fact['id']})

        ctr += 1
        detail = m[13] #
        fact['to'] = detail[1]
        fact['subject'] = detail[5]
        fact['content'] = detail[6]
        fact['src'] = 'detail'
        print "DETAIL", fact
        self.save(flow, fact, selector={'kind':'mail', 'id': fact['id']})
        ctr += 1

        return ctr
