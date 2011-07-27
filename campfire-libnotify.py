#!/usr/bin/python
import urllib2, base64, pynotify, time, os
from datetime import datetime
from xml.dom import minidom
from xml.parsers.expat import ExpatError
import logging

logging.basicConfig(level=logging.INFO)

class CampFireNotify(object):
    def __init__(self, user, domain, room, icon=None):
        self.user = user
        self.domain = domain
        self.room = room
        self.latest_entry = datetime.utcnow()
        self.user_dict = {}
        self.ignore_list = []
        self.new_messages = []
        self._recent_uri = "https://%s.campfirenow.com/room/%d/recent.xml" % (self.domain, self.room)
        self._room_uri = "https://%s.campfirenow.com/room/%d.xml" % (self.domain, self.room)
        self._auth_string = base64.encodestring('%s:x' % self.user).replace('\n', '')
        self._icon_uri = ''

    class Message(object):
        def __init__(self, **args):
            self.__dict__ = args

    def get_posts(self):
        logging.info("Checking for new posts...")

        recent_request = urllib2.Request(self._recent_uri)
        recent_request.add_header("Authorization", "Basic %s" % self._auth_string)
        try:
            recent_result = urllib2.urlopen(recent_request)
        except urllib2.HTTPError:
            logging.error("Cannot connect to %s" % recent_request.get_full_url())
            return

        room_request = urllib2.Request(self._room_uri)
        room_request.add_header("Authorization", "Basic %s" % self._auth_string)
        try:
            room_result = urllib2.urlopen(room_request)
        except urllib2.HTTPError:
            logging.error("Cannot connect to %s" % recent_request.get_full_url())
            return

        try:
            user_doc = minidom.parse(room_result)
            users = user_doc.getElementsByTagName('user')
        except ExpatError:
            logging.error("Could not parse Campfire Room XML")
        try:
            message_doc = minidom.parse(recent_result)
            messages = message_doc.getElementsByTagName('message')
        except ExpatError:
            logging.error("Could not parse Campfire Recent Messages XML")

        for user in users:
            try:
                user_id = user.getElementsByTagName('id')[0].firstChild.nodeValue
                user_name = user.getElementsByTagName('name')[0].firstChild.nodeValue
            except IndexError:
                logging.error("Could not retrieve necessary user info from XML")
            else:
                self.user_dict[user_id] = user_name

        for message in messages:
            try:
                msg_type = message.getElementsByTagName('type')[0].firstChild.nodeValue
            except IndexError:
                logging.error('Failed to get type from msg')
                continue
            if msg_type == 'TextMessage':
                try:
                    strdate = message.getElementsByTagName('created-at')[0].firstChild.nodeValue.strip()
                    date = datetime.strptime(strdate, '%Y-%m-%dT%H:%M:%SZ')
                except IndexError:
                    logging.error('Failed to get date from msg')
                    continue
                else:
                    if date <= self.latest_entry:
                        logging.info('Ignoring old entry %s' % datetime.strftime(date, '%Y-%m-%d %H:%M:%S'))
                        continue
                try:
                    body =  message.getElementsByTagName('body')[0].firstChild.nodeValue.strip()
                except IndexError:
                    logging.error('Failed to get body from msg')
                    continue
                try:
                    user_id = message.getElementsByTagName('user-id')[0].firstChild.nodeValue.strip()
                    if self.user_dict.get(user_id, '') in self.ignore_list: continue
                except IndexError:
                    logging.error('Failed to get user-id from msg')
                    continue
                try:
                    self.new_messages.append(self.Message(user=self.user_dict[user_id],body=body, date=date))
                except KeyError:
                    logging.info("Missing user %s" % user_id)
                    self.new_messages.append(self.Message(user='Unknown', body=body, date=date))

        if self.new_messages:
            self.new_messages = sorted(self.new_messages, key=(lambda x: x.date))
            self.latest_entry = self.new_messages[-1].date

    def clear_messages(self):
        self.new_messages = []

    def set_icon(self, icon_uri):
        self._icon_uri = icon_uri

    def pyNotify(self, limit=0):
        for message in self.new_messages[:limit or None]:
            notify = pynotify.Notification(message.user, message.body[:100], self._icon_uri)
            logging.info("Showing Notification: User:%s Message:%s" % (message.user, message.body[:20]))
            notify.show()

    def ignore_user(self, user_name):
        self.ignore_list.append(user_name)



if __name__ == '__main__':
    import signal
    import sys
    def exit_handler(signal, frame):
            print "\n\nSo long and thanks for all the fish\n"
            sys.exit(0)
    signal.signal(signal.SIGINT, exit_handler)

    user = "INSERT_API_KEY_HERE"
    domain = "subdomain"
    room = 1 # your room number
    cfn = CampFireNotify(user=user, domain=domain, room=room)
    cfn.ignore_user('Ryan Scarbery')
    cfn.set_icon(os.path.join(os.getcwd(), 'logo-small-campfire.gif'))
    while True:
        cfn.get_posts()
        cfn.pyNotify()
        cfn.clear_messages()
        time.sleep(10)
