from io import BytesIO
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import os, datetime, requests, json, re, bs4, pycurl, subprocess
import xml.etree.ElementTree as ET
import config.config as CONFIG

from scrape import extractName, extractLinks, extractFromXML, extractFromPubmed, makeRequest, getTreeMap
from treeMap import createTreeMap, checkDict, getLongestWord, createDict


stopwords = set(stopwords.words('english'))


REPO_FILTER_WORDS = ['github', 'bitbucket', 'sourceforge', 'bioconductor']

def filterXML(filename, cur_dir, move_dir):
	"""Move files that have one of the filter words


    Args:
        filename (str): The name of the XML file
        cur_dir (str): The directory in which the current file is in.
        move_dir (str): The directory in which you want this file to be moved to.

    Returns:
        int: Return 1 if the file was moved and has the filter word. Returns 0 if not.

    """
	if filename and os.path.isfile(cur_dir+filename):
		tree = ET.parse(cur_dir+filename)
		root = tree.getroot()
		#found = root.find("./article/front/article-meta/abstract")
		found = root.find("./article/body")
		if found is not None:
			abstract = ET.tostring(found, encoding='utf-8', method='text')
			abstract = abstract.lower()
			for word in REPO_FILTER_WORDS:
				if word in abstract:
					print(filename)
					os.rename(cur_dir+filename, move_dir+filename)
					return 1
	return 0



def getGithubData(repo_link):
	"""Extract github data given the github link

	Makes an HTTP request to github using Github REST API

    Args:
        repo_link (str): The link/url for the github repository

    Returns:
        obj: The return value is an object with the data.

    """
	reg_format = True
	m = re.search('(www\.)?github.(com|org)\/[\S]+?\/[\w.-]+', repo_link)
	if not m:
		reg_format = False
		m = re.search('[\w-]+\.github.(com|org|io)?(\/[\w-]+)*', repo_link)

	if not m:
		return {}

	filtered_repo_link = m.group(0)


	repo = ''
	if reg_format:
		repo = filtered_repo_link[filtered_repo_link.find('/')+1:]
	else:
		repo = filtered_repo_link[:filtered_repo_link.find('.')]
		slash_idx = filtered_repo_link.find('/')
		if slash_idx>0:
			repo+= filtered_repo_link[slash_idx:]
		else:
			repo = repo+'/'+repo

	if repo.endswith('.git'):
		repo = repo[:-4]

	link = 'https://api.github.com/repos/'+repo
	link+='?client_id=046041908fb0240cb92e&client_secret=5d1cf3216d6af9aff470fbb6047b1644af7c0c7f'
	try:
		r_text = makeRequest(link)
		github_obj = json.loads(r_text)
		if 'message' in github_obj and github_obj['message']=='Moved Permanently' and 'url' in github_obj:
			r_text = makeRequest(github_obj['url'])
			github_obj = json.loads(r_text)

		obj = {}
		obj['name'] = github_obj['name']
		obj['type'] = 'github'
		obj['repo_link'] = filtered_repo_link
		obj['forks'] = github_obj['forks_count']
		obj['watchers'] = github_obj['watchers_count']
		obj['owner'] = github_obj['owner']['login']
		obj['description'] = github_obj['description']
		obj['language'] = github_obj['language']
		obj['size'] = github_obj['size']
		if github_obj['created_at']:
			obj['created_at'] = github_obj['created_at']
		if github_obj['updated_at']:
			obj['updated_at'] = github_obj['updated_at']

		obj['open_issues'] = github_obj['open_issues']
		obj['homepage'] = github_obj['homepage']
		if 'license' in github_obj:
			obj['license'] = github_obj['license']['name']
		else:
			obj['license'] = 'No License'

		return obj
	except:
		return {}
	return {}

def getBitbucketData(repo_link):
	"""Extract bitbucket data given the bitbucket link

	Makes an HTTP request to github using Bitbucket REST API

    Args:
        repo_link (str): The link/url for the bitbucket repository

    Returns:
        obj: The return value is an object with the data.

    """
	m = re.search('(www\.)?bitbucket.(com|org)\/[\S]+?\/[\w.-]+', repo_link)

	repo = ''
	if not m:
		m = re.search('[\w-]+\.bitbucket.(com|org)?(\/[\w-]+)*', repo_link)
		if not m:
			return {}
		else:
			filtered_repo_link = m.group(0)
			repo = filtered_repo_link[:filtered_repo_link.find('.')]
			repo = repo+'/'+repo
	else:
		filtered_repo_link = m.group(0)
		repo = filtered_repo_link[filtered_repo_link.find('/')+1:]

	if repo.endswith('.git'):
		repo = repo[:-4]

	link = 'https://api.bitbucket.org/2.0/repositories/'+repo
	try:
		r_text = makeRequest(link)
		if r_text[0]=='{':
			bitbucket_obj = json.loads(r_text)
			obj = {}
			obj['name'] = bitbucket_obj['name']
			obj['type'] = 'bitbucket'
			obj['repo_link'] = filtered_repo_link
			obj['owner'] = bitbucket_obj['owner']['username']
			obj['description'] = bitbucket_obj['description']
			obj['language'] = bitbucket_obj['language']
			obj['size'] = bitbucket_obj['size']

			if bitbucket_obj['created_on']:
				obj['created_at'] = bitbucket_obj['created_on'].replace('+00:00', 'Z')
			if bitbucket_obj['updated_on']:
				obj['updated_at'] = bitbucket_obj['updated_on'].replace('+00:00', 'Z')
				# obj['updated_at'] = datetime.datetime.strptime(bitbucket_obj['updated_on'].split('T')[0], '%Y-%m-%d')

			obj['homepage'] = bitbucket_obj['website']
			obj['license'] = 'No License'

			r_text = makeRequest(link+'/watchers')
			obj['watchers'] = json.loads(r_text)['size']

			r_text = makeRequest(link+'/forks')
			obj['forks'] = json.loads(r_text)['size']
			return obj
		elif 'github' in r_text:
			return getGithubData(r_text[:-1])
		elif 'bitbucket' in r_text:
			return getBitbucketData(r_text[:-1])
	except:
		return {}
	return {}


def getSourceforgeData(repo_link):
	"""Extract sourceforge data given the sourceforge link

	Makes an HTTP request to github using Sourceforge REST API

    Args:
        repo_link (str): The link/url for the sourceforge repository

    Returns:
        obj: The return value is an object with the data.

	"""

	reg_format = True
	m = re.search('(www\.)?sourceforge.(com|net)\/[\S]+?\/[\w.-]+', repo_link)
	if not m:
		reg_format = False
		m = re.search('[\w-]+\.sourceforge.(com|net|io)?(\/[\w-]+)*', repo_link)

	if not m:
		return {}

	filtered_repo_link = m.group(0)

	repo = ''
	if reg_format:
		repo = filtered_repo_link[filtered_repo_link.rfind('/')+1:]
	else:
		repo = filtered_repo_link[:filtered_repo_link.find('.')]


	link = 'https://sourceforge.net/rest/p/'+repo

	try:
		r_text = makeRequest(link)
		sf_obj = json.loads(r_text)
		obj = {}

		obj['homepage'] = sf_obj['external_homepage']
		obj['repo_link'] = filtered_repo_link
		obj['type'] = 'sourceforge'

		movedToGH = False
		if obj['homepage'] and 'github' in obj['homepage']:
			obj = getGithubData(obj['homepage'])
			movedToGH = True
		elif 'github' in sf_obj['moved_to_url']:
			obj = getGithubData(sf_obj['moved_to_url'])
			movedToGH  =True


		if not movedToGH:
			obj['name'] = sf_obj['name']

			if sf_obj['developers']:
				obj['owner'] = sf_obj['developers'][0]['username']

			if sf_obj['categories']['language']:
				obj['language'] = sf_obj['categories']['language'][0]['fullname']
			else:
				obj['language'] = None

			try:
				update_link = link + '/activity'
				r_text = makeRequest(update_link)
				update_obj = json.loads(r_text)['timeline'][0]
				obj['updated_at'] = datetime.datetime.fromtimestamp(update_obj['published']/1000).strftime('%Y-%m-%dT%H:%M:%SZ')
			except:
				obj['updated_at'] = None

		if 'description' not in obj or not obj['description']:
			obj['description'] = sf_obj['short_description']



		if 'license' not in obj or obj['license']=='No License':
			if sf_obj['categories']['license']:
				obj['license'] = sf_obj['categories']['license'][0]['fullname']
			else:
				obj['license'] = 'No License'

		obj['created_at'] = datetime.datetime.strptime(sf_obj['creation_date'], '%Y-%m-%d').strftime('%Y-%m-%dT%H:%M:%SZ')

		obj['labels'] = sf_obj['labels']


		try:
			stats_link = 'https://sourceforge.net/projects/'+repo+'/files/stats/json?start_date=2000-1-1&end_date='+datetime.datetime.now().strftime('%Y-%m-%d')
			r_text = makeRequest(stats_link)
			stats_obj = json.loads(r.text)
			obj['downloads'] = stats_obj['total']
		except:
			obj['downloads'] = None

		if 'forks' not in obj:
			obj['forks'] = 0


		return obj
	except:
		return {}
	return {}

def getBioCName(name, links=[], text=''):
	"""Generates a list of names given a list of urls, text (usually abstract).

	Many times, publishers do not provide the bioconductor link for the software.
	Therefore, we must extract potential names from the available data.

    Args:
        name (str): The name that was extracted using traditional methods (via extractName)
		links ([str], optional): A list of urls to extract the name from
		text (str, optional): A body of text, usually the abstract, to extract the name

    Returns:
        [str]: A list of potential names for the bioconductor tool.

	"""

	results = []

	# if there are multiple tools
	if name:
		if name.find('&')>0:
			results+=name.split('&')
		elif name.find('and')>0:
			results+=name.split('and')
		tokens = name.split()
		# bioconductor names are case sensitive
		if tokens:
			results.append(tokens[0])
			if not tokens[0].islower():
				results.append(tokens[0].lower())

	# extract the name from the link
	for link in links:
		m = re.search('(www\.)?bioconductor.(com|org)(\/[\S]+)+', link)
		if m:
			repo_link = m.group(0)
			repo_name = repo_link[repo_link.rfind('/')+1:]
			if repo_name.endswith('.html'):
				repo_name = repo_name[:-5]
			results.append(repo_name)

	# extract the name based on known patterns used to describe a bioconductor tool
	if text:
		m = re.search('package called [\w\d-]+', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			results.append(extracted_text.split()[-1])

		m = re.search('(the|an) (r\/bioconductor|bioconductor r|r|bioconductor)( |-)package [\w\d-]+', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			results.append(extracted_text.split()[-1])

		m = re.search('availability( and implementation)?:(:)? (the |the R package |the package )*[\w\d-]+', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			extracted_name = extracted_text.split()[-1]
			results.append(extracted_name)
			if extracted_name[0].isupper():
				results.append(extracted_name[0].lower()+extracted_name[1:])

		m = re.search('the [\w\d-]+ (bioconductor r|r\/bioconductor|r|bioconductor) package', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			results.append(extracted_text.split()[1])

		m = re.search('(in|as) (the )?(bioconductor r( |-)|r\/bioconductor(-| )|r(-| )|bioconductor(-| ))package [\w\d]+', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			results.append(extracted_text.split()[-1])

		m = re.search('(bioconductor r|r\/bioconductor|r|bioconductor)( [\d.]+)? package(s)? [\w\d]+', text, re.IGNORECASE)
		if m:
			extracted_text = m.group(0)
			results.append(extracted_text.split()[-1])

		if name.islower():
			m = re.search(name, text, re.IGNORECASE)
			if m:
				extracted_text = m.group(0)
				results.append(extracted_text.split()[-1])


	return results




def getBioCData(repo_name):
	"""Extract bioconductor data given the name of the tool

	Makes an HTTP request to bioconductor; parses the html text for metadata

    Args:
        reponame (str): The name of the bioconductor tool

    Returns:
        obj: The return value is an object with the data.

	"""
	link = 'http://bioconductor.org/packages/release/bioc/html/'+repo_name+'.html'
	try:
		obj = {}

		r_text = makeRequest(link)

		soup = bs4.BeautifulSoup(r_text, 'html.parser')
		name = soup.find('h1')
		if name.string=='Page Not Found':
			return {}

		summary_element = soup.find('div' , class_='do_not_rebase')
		if summary_element:
			table_elements = summary_element.find_all('table')
			detail_table = table_elements[1]
			package_table = table_elements[2]


			row_elements = package_table.find_all('tr')

			for row_element in row_elements:
				col_elements = row_element.find_all('td')
				col_name = col_elements[0].string
				if col_name=='Git source':
					tag_element = col_elements[1].find('a')
					obj = getGithubData(tag_element.string)
					obj['git_link'] = tag_element.string

			full_name = summary_element.find('h2')
			obj['long_name'] = full_name.string

			obj['tags'] = []

			row_elements = detail_table.find_all('tr')

			for row_element in row_elements:
				col_elements = row_element.find_all('td')
				col_name = col_elements[0].string
				if col_name=='biocViews':
					tag_elements = col_elements[1].find_all('a')
					for tag_element in tag_elements:
						if not tag_element.string=='Software':
							obj['tags'].append(tag_element.string)
				elif col_name=='License':
					obj['license'] = col_elements[1].string

			p_elements = summary_element.find_all('p')
			obj['description'] = p_elements[1].string
			obj['authors'] = []
			author_text = p_elements[3].string
			author_text = author_text[author_text.find(':')+1:]
			authors = author_text.split(',')
			for author in authors:
				author_name = author.split()
				obj['authors'].append({'first_name':author_name[0], 'last_name': author_name[1]})


			stats_text = makeRequest('http://bioconductor.org/packages/stats/')
			m = re.search(name.string+'&nbsp;\([\d]+\)', stats_text)

			if m:
				tool_stat_text = m.group(0)
				obj['downloads'] = int(tool_stat_text[tool_stat_text.find('(')+1:tool_stat_text.find(')')])

		obj['name'] = name.string
		obj['repo_link'] = link
		obj['language'] = 'R'
		obj['type'] = 'bioconductor'

		if 'forks' not in obj:
			obj['forks'] = 0



		return obj
	except:
		return {}
	return {}


def getCrossRefInfo(doi):
	"""Get information from Crossref regarding a publication

	Makes an HTTP request using Crossref API

    Args:
        doi (str): The doi for the specific publication

    Returns:
        obj: The return value is an object with the data.

	"""
	link = 'https://api.crossref.org/works/'
	r_text = makeRequest(link+doi)

	result = {}
	try:
		json_body = json.loads(r_text)
		content = json_body['message']

		result['citations'] = content['is-referenced-by-count']
		result['references'] = content['references-count']
		result['domain'] = content['subject']
	except:
		return {}

	return result



def loadInstitutions(filename):
	"""Creates a dictionary of institution aliases


    Args:
        filename (str): The path of the file (json) containing institutions and their aliases.
		[
			{
				'name': 'Harvard University'
				'aliases': ['Harvard']
			},...
		]

    Returns:
        dict: The return value is a dictionary of institutions.
		{
			'Harvard': 'Harvard University',
			'Harvard University': 'Harvard University'
		}

	"""
	results = {}
	with open(filename) as f:
		data = json.load(f)
		results[entry['name'].lower()] = entry['name']
		for entry in data:
			for a in entry['aliases']:
				results[a.lower()] = entry['name']

	return results




def generateCompleteJSON(pmid='', pmc='', doi='', source='PMC Extraction'):
	"""Aggregates all information about a publication, including
	Publication information from Pubmed, CrossRef info, and code
	repo info from Github, Bitbucket, Sourceforge, and Bioconductor.
	Either a PMID or PMC ID should be provided.


    Args:
        pmid (str, optional): The pmid for the specific publication
		pmc (str, optional): The PMC ID (if any) for the specific publication
		doi (str, optional): The DOI for the specific publication
		source (str, optional): The name of the source or method used to extract the data.

    Returns:
        obj: The return value is an object with the data.

	"""
	pub = {}

	# extract metadata from Pubmed
	if pmc:
		pub = extractFromPubmed('', pmc=pmc)
	elif pmid:
		pub = extractFromPubmed(pmid)
	elif doi:
		pub = extractFromPubmed('', doi=doi)
	else:
		return {}

	if not pub or 'doi' not in pub:
		return {}

	# extract the name of the tool
	name = extractName(pub['title'], pub['abstract'], repo=pub['repo'],
		links=[link['link'] for link in pub['links']])

	# check if institution is in tree map data structure
	institutions = []

	for instit in pub['institutions']:
		tokens = instit.split(',')
		temp_map = getTreeMap()
		if len(tokens)>4:
			tokens = tokens[:-3]
		for token in tokens:
			token = token.strip().lower()
			filter_token = re.sub('[-–]', ' ', token)
			temp_map = checkDict(filter_token.split(), temp_map)
			if type(temp_map)==type({}):
				continue
			elif temp_map:
				institutions.append(temp_map)
				break
			else:
				temp_map = getTreeMap()

	# get code repo info
	obj = {}
	for link in pub['links']:
		if pub['repo']=='github':
			obj = getGithubData(link['link'])
		elif pub['repo']=='bitbucket':
			obj = getBitbucketData(link['link'])
		elif pub['repo']=='sourceforge':
			obj = getSourceforgeData(link['link'])

		if obj:
			break

	if pub['repo']=='bioconductor':
		if not name:
			name = ['']
		names = getBioCName(name[0], [l['link'] for l in pub['links']], pub['abstract'])
		for n in names:
			obj = getBioCData(n)
			if obj:
				break


	# get cross ref info
	cr_obj = getCrossRefInfo(pub['doi'])

	entry = {}
	if name:
		entry['name'] = name[0]
	else:
		entry['name'] = ''

	entry['description'] = pub['abstract']
	entry['publication'] = {}
	entry['source'] = source
	entry['dateCreated'] = pub['dateCreated']
	entry['dateUpdated'] = pub['dateUpdated']
	entry['publication']['journal'] = pub['journal']
	entry['publication']['title'] = pub['title']
	entry['publication']['pmid'] = pub['pmid']
	entry['publication']['doi'] = pub['doi']
	entry['publication']['date'] = pub['date']
	entry['institutions'] = list(set(institutions))
	entry['links'] = pub['links']
	entry['emails'] = pub['emails']
	entry['tags'] = pub['tags']
	entry['funding'] = pub['funding']
	entry['authors'] = pub['authors']
	entry['repo'] = obj or {}
	entry['repo']['type'] = pub['repo']
	if cr_obj:
		entry['domains'] = cr_obj['domain']
		entry['publication']['citations'] = cr_obj['citations']
		entry['publication']['references'] = cr_obj['references']
	else:
		entry['domains'] = []
		entry['publication']['citations'] = 0
		entry['publication']['references'] = 0


	return entry



def pushToSolr(entry, checkCollisions=False, update=False, ignoreMissing=False):
	"""Adds new entry to the Solr hosted locally; allows options to check if the
	entry has a collision in Solr; update an entry rather than create a new entry;
	ignore missing essential metadata fields

	Uses curl to POST entry to Solr on localhost:8983/BD2K

    Args:
        entry (dict): The json object (in the Solr schema) to be pushed to Solr
		checkCollisions (bool, optional): If True, do not add entry if entry has DOI in Solr. Default is False.
		update (bool, optional): If True, update Solr with the entry that has the same DOI. Default is False
		ignoreMissing (bool, optional): If True, allows entry to be pushed to Solr even if essential metadata is missing. Default is False.

    Returns:
        int: Returns 1 if the entry was pushed to Solr. Otherwise, return 0.

	"""

	# uf repo information is not provided
	if 'repo' not in entry or not entry['repo'] or 'codeRepoURL' not in entry:
		hasRepo = False
		# check if any of the links has a repo
		if 'linkUrls' in entry:
			for link in entry['linkUrls']:
				foundRepo = False
				for word in REPO_FILTER_WORDS:
					if word in link:
						hasRepo = True
						foundRepo = True
						break
				if foundRepo:
					break
		# do not push if no repo and ignoreMIssing flag is True
		if not hasRepo and not ignoreMissing:
			print(entry['publicationDOI'], 'does not have repo info')
			return 0

	foundEntry = False
	# check if there is checkCollisions
	# only if update=True or checkCollisions=True
	if 'publicationDOI' in entry and entry['publicationDOI'] and (update or checkCollisions):
		doi = entry['publicationDOI'][0]
		link = CONFIG.NEW_SOLR_URL+'select?q=publicationDOI%3A'+'"'+doi+'"'+'&fl=publicationDOI%2Cid&wt=json&indent=true'
		r_text = makeRequest(link)
		try:
			json_body = json.loads(r_text)
			if json_body['response']['numFound']>0:
				foundEntry = True
				# if there are no links or if the checkCollisions=True
				if checkCollisions or len(entry['linkUrls'])==0:
					return 0
				else:
					entry['id'] = json_body['response']['docs'][0]['id']
					print('update', entry['id'])
		except:
			print('Could not query', link)

	# if a collision was not found, assign a new id to entry
	if not foundEntry:
		id = getHighestSolrID()+1
		entry['id'] = id

	input = json.dumps(entry)
	# Call curl to post entry
	subprocess.call(
        [
            "curl",
            "-X",
            "-POST",
            "-H",
            "Content-Type: application/json",
            CONFIG.NEW_SOLR_URL +
            "update/json/docs/?commit=true",
            "--data-binary",
            input
        ])
	return 1

def convertToSolr_Repo(obj):
	"""Helper function to convert an object to the Solr (schema) format

    Args:
        obj (dict): The json object with repo info

    Returns:
        dict: Returns an object in the Solr format

	"""
	solr_entry = {}

	if 'repo_link' in obj:
		solr_entry['repo'] = obj['type']
		solr_entry['codeRepoURL'] = obj['repo_link']
		if 'owner' in obj:
			solr_entry['repoOwner'] = obj['owner']

		if 'language' in obj:
			solr_entry['language'] = [obj['language']]

		if 'description' in obj:
			solr_entry['repoDescription'] = obj['description']

		solr_entry['repoName'] = obj['name']
		solr_entry['name'] = solr_entry['repoName']

		if 'homepage' in obj:
			solr_entry['repoHomepage'] = obj['homepage']

		if 'created_at' in obj:
			solr_entry['repoCreationDate'] = obj['created_at']
			solr_entry['repoUpdatedDate'] = obj['updated_at']
		if 'downloads' in obj:
			solr_entry['repoDownloads'] = obj['downloads'] or 0
		if 'forks' in obj:
			solr_entry['repoForks'] = obj['forks'] or 0

	return solr_entry

def converToSolrFormat(entry):
	"""Convert the entry to the Solr format that conforms to the Solr schema


    Args:
        entry (dict): The json object that is to be converted Solr format

    Returns:
        dict: Returns an object in the Solr schema format.

	"""
	solr_entry = {}

	solr_entry['name'] = ''
	if 'repo' in entry and 'type' in entry['repo'] and not entry['repo']['type']=='':
		solr_entry.update(convertToSolr_Repo(entry['repo']))
	else:
		if 'publication' not in entry:
			return {'publicationDOI': ''}
		return {'publicationDOI':entry['publication']['doi']}


	solr_entry['name'] = solr_entry['name'] or entry['name']
	solr_entry['description'] = entry['description']
	solr_entry['institutions'] = entry['institutions']
	solr_entry['tags'] = entry['tags']
	solr_entry['emails'] = entry['emails']
	solr_entry['source'] = entry['source']
	solr_entry['domains'] = entry['domains']
	solr_entry['dateCreated'] = entry['dateCreated']
	solr_entry['dateUpdated'] = entry['dateUpdated']

	solr_entry['linkUrls'] = []
	for link in entry['links']:
		if not link['broken']:
			solr_entry['linkUrls'].append(link['link'])

	solr_entry['linkUrls'] = list(set(solr_entry['linkUrls']))

	solr_entry['publicationDOI'] = [entry['publication']['doi']]
	solr_entry['publicationTitle'] = [entry['publication']['title']]
	solr_entry['publicationDate'] = [entry['publication']['date']]
	solr_entry['publicationJournal'] = [entry['publication']['journal']]
	solr_entry['publicationPMID'] = [entry['publication']['pmid']]
	solr_entry['publicationReferences'] = [entry['publication']['references']]



	solr_entry['authors'] = []
	for author in entry['authors']:
		solr_entry['authors'].append(author['first_name']+' '+ author['last_name'])

	solr_entry['funding'] = []
	solr_entry['fundingAgencies'] = []
	for fund in entry['funding']:
		if fund[0]=='Agency not found':
			continue
		solr_entry['fundingAgencies'].append(fund[0])
		solr_entry['funding'].append(fund[0]+': '+fund[1])

	solr_entry['fundingAgencies'] = list(set(solr_entry['fundingAgencies']))

	return solr_entry

def getHighestSolrID():
	"""Query Solr (hosted on localhost) to retrieve the highest ID value

    Args:
        None

    Returns:
        int: Returns the value of the largest ID in Solr

	"""
	link = CONFIG.NEW_SOLR_URL+'select?q=*%3A*&fl=id&wt=json&indent=true&sort=id+desc&rows=1'
	result = makeRequest(link)
	json_body = json.loads(result)

	if json_body['response']['docs']:
		return json_body['response']['docs'][0]['id']

	return 0

def migrateOldEntries(old_entry):
	"""Converts the old entry to the new Solr format entry


    Args:
        old_entry (dict): The json object (in the old Solr schema) to be converted to the new Solr format

    Returns:
        dict: The converted Solr-formatted object

	"""

	if not old_entry:
		return None

	new_entry = {}
	new_entry['publicationDOI'] = []
	# if a DOI is provided, query PubMed for metadata
	if 'publicationDOI' in old_entry and old_entry['publicationDOI']:
		# clean up the publicationDOI
		doi = old_entry['publicationDOI'].lower()
		if doi.startswith('doi:'):
			doi = doi[4:]
		doi = doi.strip()
		if ' ' in doi:
			doi = doi.split()[0]

		new_entry = converToSolrFormat(generateCompleteJSON('', doi=doi))
		new_entry['publicationDOI'] = [doi]
		# consolidate metadata if the old entry is user submitted
		if old_entry['source']=='User Submission':
			new_entry['source'] = old_entry['source']
			new_entry['name'] = old_entry['name']
			new_entry['description'] = old_entry['description']

			sourceCodeURLs = []
			if 'sourceCodeURL' in old_entry:
				sourceCodeURLs = old_entry['sourceCodeURL']

			old_links = []
			if 'linkUrls' in old_entry:
				old_links = old_entry['linkUrls']

			new_links = []
			if 'linkUrls' in new_entry:
				new_links = new_entry['linkUrls']
			new_entry['linkUrls'] = list(set(old_links+new_links+sourceCodeURLs))

			if 'tags' in new_entry and 'tags' in old_entry:
				new_entry['tags'] = list(set(old_entry['tags']+new_entry['tags']))
			elif 'tags' in old_entry:
				new_entry['tags'] = old_entry['tags']

			if 'domains' in new_entry and 'domains' in old_entry:
				new_entry['domains'] = list(set(old_entry['domains']+new_entry['domains']))
			elif 'domains' in old_entry:
				new_entry['domains'] = old_entry['domains']

			if 'language' in new_entry and 'language' in old_entry:
				new_entry['language'] = list(set(old_entry['language']+new_entry['language']))
			elif 'language' in old_entry:
				new_entry['language'] = old_entry['language']

	# if you cannot retrieve entry from Pubmed
	if 'name' not in new_entry or 'sourceCodeURL' not in new_entry:
		new_entry['name'] = old_entry['name']
		if old_entry['source']=='Bioinformatics [Journal]':
			new_entry['source'] = 'Grobid Extraction: Bioinformatics'
		else:
			new_entry['source'] = old_entry['source']

		if 'description' in old_entry:
			new_entry['description'] = old_entry['description']

		sourceCodeURLs = []
		if 'sourceCodeURL' in old_entry:
			sourceCodeURLs = old_entry['sourceCodeURL']

		if 'linkUrls' in old_entry:
			new_entry['linkUrls'] = list(set(old_entry['linkUrls']+sourceCodeURLs))
		else:
			new_entry['linkUrls'] = sourceCodeURLs

		if 'tags' in old_entry:
			new_entry['tags'] = old_entry['tags']
		else:
			new_entry['tags'] = []

		new_entry['authors'] = []
		if 'authors' in old_entry:
			for author in old_entry['authors']:
				new_entry['authors'].append(author.strip())

		new_entry['institutions'] = []
		if 'institutions' in old_entry:
			for institution in old_entry['institutions']:
				new_entry['institutions'].append(institution.strip())

		new_entry['funding'] = []
		funding_set = set()
		agencies = set()
		if 'funding' in old_entry:
			for funding in old_entry['funding']:
				comma_idx = funding.find(',')
				agency = funding[funding.find('[')+1:comma_idx]
				if agency=='Agency not found':
					continue
				grant = funding[comma_idx+1:-1]

				agencies.add(agency)
				if grant.find('Grant not found') < 0:
					funding_set.add(agency+':'+grant)

		new_entry['funding'] = list(funding_set)
		new_entry['fundingAgencies'] = list(agencies)

		if 'dateCreated' in old_entry:
			new_entry['dateCreated'] = old_entry['dateCreated'][0]

		if 'dateUpdated' in old_entry:
			new_entry['dateUpdated'] = old_entry['dateUpdated'][0]
		else:
			new_entry['dateUpdated'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

		if 'domains' in old_entry:
			new_entry['domains'] = old_entry['domains']

		# check all links to see if they are code repo links
		# if so, get code repo metdata
		obj = {}
		isBioC = False
		for link in new_entry['linkUrls']:
			if 'github' in link:
				obj = getGithubData(link)
			elif 'bitbucket' in link:
				obj = getBitbucketData(link)
			elif 'sourceforge' in link:
				obj = getSourceforgeData(link)
			elif 'bioconductor' in link:
				isBioC = True

			if obj or isBioC:
				break

		if isBioC:
			names = getBioCName(new_entry['name'], new_entry['linkUrls'], new_entry['description'])
			for n in names:
				obj = getBioCData(n)
				if obj:
					break
		if obj:
			new_entry.update(convertToSolr_Repo(obj))
			new_entry['dateUpdated'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')


	return new_entry




# pm_obj = extractFromPubmed(18227117, pmc='2579711')
# print(json.dumps(pm_obj, indent=2))

# entries = generateJSON(using_dir, journal='Bioinformatics', source='PMC Extraction')
# print(json.dumps(entries, indent=2))
#
# totalAdded = 0
# for entry in entries:
# 	converted_entry = converToSolrFormat(entry)
# 	status = pushToSolr(converted_entry)
# 	if not status:
# 		print(json.dumps(entry, indent=2))
# 	totalAdded+=status
# print(totalAdded, 'new entries added')
# pushToSolr_safe({'publicationDOI': '10.1093/bioinformatics/btp104', 'repo':123})

	# print(json.dumps(converted_entry, indent=2))
# print(getHighestSolrID())
# createTreeMap('./inst_alias.json')
# print(getFirstValue(my_tree_map['max']['planck']))
# print(checkDict(['university', 'of', 'california', 'san', 'diego'], my_tree_map))
# print(checkDict(['university', 'of', 'california', 'san', 'francisco'], my_tree_map))
# print(checkDict(['the'], my_tree_map))
# print(getLongestWord(['university', 'of', 'california', 'san', 'diego', 'aasdf', 'asdf']))
# d = {'U':{'C':{'S':{'D':{'$value':'ucsd'}}}}}
# d1 = createDict({}, ['U', 'C','S','F'], 'ucsf')
# print(createDict(d1, ['U', 'C','S','D'], 'ucsd'))
# print(createDict(d1, ['U', 'C'], 'ucsf'))
# print(checkDict(['U', 'C','S','D'], d1))
