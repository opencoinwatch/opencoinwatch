from django.conf import settings

import http.client
import urllib
import tweepy


def send_pushover_notification(text):
    if not settings.PRODUCTION:
        print("Won't send notification in testing environment.")
        return

    print("Sending notification...")
    conn = http.client.HTTPSConnection('api.pushover.net:443')
    conn.request('POST', '/1/messages.json',
        urllib.parse.urlencode({
            'token': settings.PUSHOVER_API_TOKEN,
            'user': settings.PUSHOVER_USER_KEY,
            'message': text,
            'url': 'https://opencoinwatch.herokuapp.com/validating/',
        }), {'Content-type': 'application/x-www-form-urlencoded'})
    conn.getresponse()
    print("...notification sent.")


def post_tweet(text):
    if not settings.PRODUCTION:
        print("Won't post tweet in testing environment.")
        return

    auth = tweepy.OAuthHandler(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET)
    auth.set_access_token(settings.TWITTER_ACCESS_TOKEN, settings.TWITTER_ACCESS_SECRET)
    api = tweepy.API(auth)
    api.update_status(text)
