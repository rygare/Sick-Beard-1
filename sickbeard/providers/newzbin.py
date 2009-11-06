import os.path
import re
import sys
import time
import urllib

import midgetpvr

from midgetpvr import exceptions, helpers, classes
from midgetpvr.common import *
from midgetpvr.logging import *

def isActive():
	return midgetpvr.NEWZBIN

class NewzbinDownloader(urllib.FancyURLopener):

	def __init__(self):
		urllib.FancyURLopener.__init__(self)
	
	def http_error_default(self, url, fp, errcode, errmsg, headers):
	
		# if newzbin is throttling us, wait 61 seconds and try again
		if errcode == 400:
		
			if int(headers.getheader('X-DNZB-RCode')) == 450:
				rtext = str(headers.getheader('X-DNZB-RText'))
				result = re.search("wait (\d+) seconds", rtext)
				
			Logger().log("Newzbin throttled our NZB downloading, pausing for " + result.group(1) + "seconds")
			
			time.sleep(int(result.group(1)))
		
			raise exceptions.NewzbinAPIThrottled

def downloadNZB(nzb):

	Logger().log("Downloading an NZB from newzbin at " + nzb.url)

	fileName = os.path.join(midgetpvr.NZB_DIR, helpers.sanitizeFileName(nzb.fileName()))
	Logger().log("Saving to " + fileName, DEBUG)

	urllib._urlopener = NewzbinDownloader()

	params = urllib.urlencode({"username": midgetpvr.NEWZBIN_USERNAME, "password": midgetpvr.NEWZBIN_PASSWORD, "reportid": nzb.extraInfo[0]})
	try:
		urllib.urlretrieve("http://v3.newzbin.com/api/dnzb/", fileName, data=params)
	except exceptions.NewzbinAPIThrottled:
		Logger().log("Done waiting for Newzbin API throttle limit, starting downloads again")
		downloadNZB(nzb)
	except (urllib.ContentTooShortError, IOError) as e:
		Logger().log("Error downloading NZB: " + str(sys.exc_info()) + " - " + str(e), ERROR)
		return False
	
	#TODO: check for throttling, wait if needed

	return True
		
def findNZB(episode, forceQuality=None):

	Logger().log("Searching newzbin for " + episode.prettyName())

	if forceQuality != None:
		epQuality = forceQuality
	else:
		epQuality = episode.show.quality
		
	if epQuality == SD:
		qualAttrs = "(Attr:VideoF~XviD OR Attr:VideoF~DivX) NOT Attr:VideoF~720p NOT Attr:VideoF~1080p Attr:Lang=Eng "
		# don't allow subtitles for SD content cause they'll probably be hard subs
		qualAttrs += "NOT (Attr:SubtitledLanguage~French OR Attr:SubtitledLanguage~Spanish OR Attr:SubtitledLanguage~German OR Attr:SubtitledLanguage~Italian OR Attr:SubtitledLanguage~Danish OR Attr:SubtitledLanguage~Dutch OR Attr:SubtitledLanguage~Japanese OR Attr:SubtitledLanguage~Chinese OR Attr:SubtitledLanguage~Korean OR Attr:SubtitledLanguage~Russian OR Attr:SubtitledLanguage~Polish OR Attr:SubtitledLanguage~Vietnamese OR Attr:SubtitledLanguage~Swedish OR Attr:SubtitledLanguage~Norwegian OR Attr:SubtitledLanguage~Finnish OR Attr:SubtitledLanguage~Turkish OR Attr:SubtitledLanguage~Unknown) "
	elif epQuality == HD:
		qualAttrs = "Attr:VideoF~x264 Attr:VideoF~720p Attr:Lang=Eng "
	else:
		qualAttrs = "(Attr:VideoF~x264 OR Attr:VideoF~XviD OR Attr:VideoF~DivX) "

	# if it's in the disc backlog then limit the results to disc sources only 
	if episode.status == DISCBACKLOG:
		qualAttrs += "(Attr:VideoS=DVD OR Attr:VideoS=Blu OR Attr:VideoS=HD-DVD) "

	q = qualAttrs
	q += "^{0} {1}x{2:0>2}".format(episode.show.name, episode.season, episode.episode)
	
	newzbinURL = {
	  'q': q,
    'searchaction': 'Search',
    'fpn': 'p',
    'category': 8,
    'area':-1,
    'u_nfo_posts_only': 0,
    'u_url_posts_only': 0,
    'u_comment_posts_only': 0,
    'sort': 'ps_edit_date',
    'order': 'desc',
    'areadone':-1,
    'feed': 'csv'}

	myOpener = classes.AuthURLOpener(midgetpvr.NEWZBIN_USERNAME, midgetpvr.NEWZBIN_PASSWORD)
	searchStr = "http://v3.newzbin.com/search/?%s" % urllib.urlencode(newzbinURL)
	Logger().log("Search string: " + searchStr, DEBUG)
	try:
		f = myOpener.openit(searchStr)
	except (urllib.ContentTooShortError, IOError) as e:
		Logger().log("Error loading search results: " + str(sys.exc_info()) + " - " + str(e), ERROR)
		return []
	rawResults = [[y.strip("\"") for y in x.split(",")] for x in f.readlines()]
	
	#TODO: check for throttling, wait
	
	results = []
	
	Logger().log("rawResults: " + str(rawResults))
	
	for curResult in rawResults:
		
		Logger().log("Found report number " + str(curResult[2]) + " at " + curResult[4] + " (" + curResult[5] + ")")
		
		result = midgetpvr.classes.NZBSearchResult(episode)
		result.provider = NEWZBIN
		result.url = curResult[4]
		result.extraInfo = [curResult[2], curResult[5]]
		
		results.append(result)
	
	return results
