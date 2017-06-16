import json, os, re, nltk, datetime, pycurl, random
from io import BytesIO


#url regex
import utilities.urlRegex as regex

from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords, words
english_words = set(words.words())
stopwords = set(stopwords.words('english'))

import xml.etree.ElementTree as ET

from treeMap import createTreeMap, checkDict, getLongestWord
import config.config as CONFIG

REPO_FILTER_WORDS = ['github', 'bitbucket', 'sourceforge', 'bioconductor']

my_tree_map = createTreeMap('./utilities/inst_alias.json')

def extractLinks(text, fileXML=None, searchFull=False):
    """Extract links (URLs) from text

    This function will use regular expressions to extract links from a
    string of text. An option is provided to pass in an xml file (PMC article)
    to extract links.

    Args:
        text (str): A body of text, usually the abstract. Can also be full paper.
        fileXML (xml.etree.ElementTree, optional): An xml object of the
        PMC-formatted XML. Defaults to None.
        searchFull (bool, optional): If True and an XML is provided, it will search
        the full text, not just the abstract. Defaults to False.


    Returns:
        ([str], [str]): The return value as a pair. The first value is a list of
        links/urls. The second value is a list of emails.


    """
    # return values
    links = []
    emails = []

    # keep track of code repo links
    foundRepo = False
    # if an xml is provided, extract all links and emails
    if fileXML:
        link_node = fileXML.findall("./article/front/article-meta/abstract/p/ext-link")

        # if no link is found in abstract, search in full text of paper
        if not link_node:
            link_node = fileXML.findall("./article/front/article-meta/abstract/sec/p/ext-link")

        # look in full text if searchFull is true
        if searchFull:
            if link_node:
                link_node += fileXML.findall("./article/body/sec/p/ext-link")
            else:
                link_node = fileXML.findall("./article/body/sec/p/ext-link")

        # extract values from link nodes
        for link in link_node:
            link_text = link.attrib['{http://www.w3.org/1999/xlink}href']
            if link_text:
                if link_text[-1]=='/':
                    link_text = link_text[:-1]
                for word in REPO_FILTER_WORDS:
                    if word in link_text:
                        foundRepo = True
                if not link_text.lower()=='supplementary data':
                    links.append((link_text, link_text[link_text.rfind('/')+1:]))

        # look for email tags in xml
        email_node = fileXML.findall("./article/front/article-meta/abstract/p/email")
        if searchFull:
            if email_node:
                email_node += fileXML.findall("./article/body/sec/p/email")
            else:
                email_node = fileXML.findall("./article/body/sec/p/email")

        for email in email_node:
            emails.append(email.text)

    if not fileXML or not foundRepo:
        # use regular expressions to find urls and emails in text
        regex_url = re.compile(regex.URL_REGEX)
        emails = re.compile(regex.EMAIL_REGEX).findall(text)
        for link in regex_url.findall(text):
            # remove trailing slash
            if link[-1]=='/':
                link = link[:-1]
            # if the link that is found is part of an email, ignore it
            isPartOfEmail = False
            for email in emails:
                if link in email:
                    isPartOfEmail = True
            if not isPartOfEmail:
                links.append((link, link[link.rfind('/')+1:]))


    return (links, emails)


def extractRepoLinks(repo, abstract=None, links=[]):
    """Extract code repository links (URLs) from text

    This function will use regular expressions to extract repo links from a
    string of text.

    Args:
        repo (str): The type of repo specified. [github, bitbucket, sourceforge]
        abstract (str, optional): The text that you would like to extract the links from.
        Default is None.
        links ([str], optional): An array of links/urls. Default is an empty list.


    Returns:
        ([(str, str)], [(str, str)]): The return value as a pair. The first value is a list of
        links/urls and the extracted names from the specified repo.
        The second value is a list of links/urls and the extracted names that are not in the specified repo.


    """
    # if an abstract is provided, extract links from the abstract
    if abstract:
        pairs = extractLinks(abstract)[0]
        links += [link[0] for link in pairs]

    results = []

    # for each type of repo, extract the repo link
    if repo=='github':
        results = extractGithub(links)
    elif repo=='bitbucket':
        results = extractBitbucket(links)
    elif repo=='sourceforge':
        results = extractSourceforge(links)

    nonRepo = []
    # for non-repo links, put in nonRepo array
    for link in pairs:
        if not repo in link[0].lower():
            nonRepo.append(link)

    return (results, nonRepo)

def extractGithub(links):
    """Check if links are valid github links

    This function will use regular expressions to extract github links and extract
    the name of the repo.

    Args:
        links ([str]): A list of strings that are formatted as links/urls.


    Returns:
        [(str, str)]: The return value as list of pairs. In each pair:
        first value is the github link, and the second value is the name of the repo.

    """
    results = []
    for link in links:
        # for links that look like github.com/user/project
        m = re.search('(www\.)?github.(com|org)\/[\S]+?\/[\w.-]+', link)
        github_name = ''
        github_link=''
        if m:
            github_link = m.group(0)
            github_name = github_link[github_link.rfind('/')+1:]
        else:
            # for links that look like github.com/user
            m = re.search('(www\.)?github.(com|org)\/[\w\d-]+', link)
            if m:
                github_link = m.group(0)
                github_name = github_link[github_link.rfind('/')+1:]
        if not m:
            # for links that look like project.github.com/subproject
            m = re.search('[\w-]+\.github.(com|org|io)?(\/[\w-]+)*', link)
            if m:
                github_link = m.group(0)
                github_name = github_link[:github_link.find('.')]
                if github_link.find('github.com')+12<len(github_link):
                    start = github_link.rfind('/')+1
                    github_name = github_link[start:]

        # remove trailing .git
        if github_name.endswith('.git'):
            github_name = github_name[:-4]

        if not github_link == "":
            results.append((github_link, github_name))

    return results

def extractBitbucket(links):
    """Check if links are valid bitbucket links

    This function will use regular expressions to extract bitbucket links and extract
    the name of the repo.

    Args:
        links ([str]): A list of strings that are formatted as links/urls.


    Returns:
        [(str, str)]: The return value as list of pairs. In each pair:
        first value is the bitbucket link, and the second value is the name of the repo.

    """

    results = []
    for link in links:
        # for links that look like bitbucket.org/user/project
        m = re.search('(www\.)?bitbucket.(com|org)\/[\S]+?\/[\w.-]+', link)
        bb_name = ''
        bb_link=''
        if m:
            bb_link = m.group(0)
            bb_name = bb_link[bb_link.rfind('/')+1:]
        else:
            # for links that look like project.bitbucket.com/subproject
            m = re.search('[\w-]+\.bitbucket.(com|org)?(\/[\w-]+)*', link)
            if m:
                bb_link = m.group(0)
                bb_name = bb_link[:bb_link.find('.')]
                if bb_link.find('bitbucket.org')+15<len(bb_link):
                    start = bb_link.rfind('/')+1
                    bb_name = bb_link[start:]

        # remove trailing .git
        if bb_name.endswith('.git'):
            bb_name = bb_name[:-4]
        if not bb_link == "":
            results.append((bb_link, bb_name))
    return results

def extractSourceforge(links):
    """Check if links are valid sourceforge links

    This function will use regular expressions to extract ): links and extract
    the name of the repo.

    Args:
        links ([str]): A list of strings that are formatted as links/urls.


    Returns:
        [(str, str)]: The return value as list of pairs. In each pair:
        first value is the ): link, and the second value is the name of the repo.

    """
    results = []
    for link in links:
        # for links that look like sourceforge.net/project
        m = re.search('(www\.)?sourceforge.(com|net)\/[\S]+?\/[\w.-]+', link)
        sf_name = ''
        sf_link=''
        if m:
            sf_link = m.group(0)
            sf_name = sf_link[sf_link.rfind('/')+1:]
        else:
            # for links that look like project.sourceforge.net/subproject
            m = re.search('[\w-]+\.sourceforge.(com|net)?(\/[\w-]+)*', link)
            if m:
                sf_link = m.group(0)
                sf_name = sf_link[:sf_link.find('.')]
                start = 0

                if sf_link.find('sourceforge.net')+17<len(sf_link):
                    start = sf_link.rfind('/')+1
                    sf_name = sf_link[start:]

        if not sf_link == "":
            results.append((sf_link, sf_name))
    return results

def extractFromTitle(title):
    """Extract the name of the tool from the title

    Tool names are extracted using known patterns.

    Args:
        title (str): The title of the publication that contains the tool.


    Returns:
        str: The return value is the extracted name from the title.
        May be blank '' if no name was found.


    """
    # remove trailing period
    period_idx = title.rfind('.')
    if period_idx>0 and period_idx>len(title)-5:
        title = title[:period_idx]

    # store value of name
    name = ''
    words = title.split()

    # if title has less than 5 words, then the title is the name of the tool
    if len(words) < 5:
        return title

    # the word(s) before the colon is the name
    colon_idx = title.rfind(':')
    if colon_idx>0:
        return title[:colon_idx]

    # a version of the title with no unicode
    noUniTitle = re.sub(r'[^\x00-\x7F]+',' ', title)

    # the word(s) before the different versions of dashes is the name
    oneDash_idx = noUniTitle.find(' - ')
    if oneDash_idx>0:
        return noUniTitle[:oneDash_idx]

    longDash_idx = title.find('–')
    if longDash_idx>0:
        return title[:longDash_idx]

    medDash_idx = title.find('—')
    if medDash_idx>0:
        return title[:medDash_idx]

    doubleDash_idx = title.find('--')
    if doubleDash_idx>0:
        return title[:doubleDash_idx]


    # the word(s) in parentheses is the name
    paren_idx = title.find('(')
    if paren_idx > 0:
        end_paren_idx = title.find(')')
        return title[paren_idx+1:end_paren_idx]

    # the word(s) following the word 'with' is the name
    with_idx = title.rfind('with')
    comma_idx = title.find(',')
    if with_idx > 0 and comma_idx < 0:
        with_name = title[with_idx+len('with '):].strip()
        if len(with_name.split()) < 3:
            return with_name

    # the word(s) before the comma is the name
    if comma_idx > 0 and title.count(',')==1:
        return title[:comma_idx]

    # the word(s) following the word 'using' is the name
    using_idx = title.find('using')
    if using_idx>0:
        using_name = title[using_idx+len('using'):].strip()
        if len(using_name.split()) < 2:
            return using_name

    # looks at the first word
    # if the word has a mix of upper and lower case letters, it is a name
    first = words[0]
    if words[0]=='The' or words[0]=='A':
        first = words[1]

    if first.isupper():
        return first
    else:
        numUpper = 0
        changes = 0
        isUpper = first[0].isupper()
        for i in range(1, len(first)):
            if isUpper:
                numUpper+=1

            if not isUpper==first[i].isupper():
                changes+=1
            isUpper = first[i].isupper()

        if changes > 1 or isUpper>2:
            return first

    return name

def extractName(title, abstract, repo='', links=[]):
    """Extract the name of the tool from the title and abstract

    Tool names are extracted using known patterns.

    Args:
        title (str): The title of the publication that contains the tool.
        abstract (str): The abstract (or full text) of the publication that contains the tool.
        repo (str, optional):
        links ([str], optional): A list of links/urls. Default is an empty list.


    Returns:
        [str]: The return value is a list of extracted names.
        Names that are most likely appear first.


    """
    results = []
    # extract a name from the title
    title_name = extractFromTitle(title)
    if title_name:
        results.append(title_name)

    # check if the words in the title are english
    # non english words are more likely to be names
    title_name_is_word = True
    words_in_name = title_name.split()
    for word in words_in_name:
        if word.lower() not in english_words:
            title_name_is_word = False
            break

    # if repo was not specified, perform search through abstract
    if not repo:
        abstract_lower = abstract.lower()
        if 'github' in abstract_lower:
            repo = 'github'
        elif 'sourceforge' in abstract_lower:
            repo = 'sourceforge'
        elif 'bitbucket' in abstract_lower:
            repo = 'bitbucket'


    # search for names in the links
    linkNames = extractRepoLinks(repo, abstract, links)
    repoNames = linkNames[0]
    regLinkNames = linkNames[1]

    # check if the title has a colon or double dash
    hasColon = title.find(':')>0
    hasDoubleDash = title.find('--')>0

    # check the ratio of words that start with uppercase letter
    numUpper = 0
    upperRatio = 0
    if words_in_name:
        for word in words_in_name:
            if word[0].isupper():
                numUpper+=1
        upperRatio = numUpper/len(words_in_name)

    # process names extracted from repo links
    if repoNames:
        if (not hasDoubleDash and upperRatio<0.5 and \
        repoNames[0][1] not in english_words and \
        (title_name_is_word or len(words_in_name)>5)) or \
        title_name in repoNames[0][1]:
            results.insert(0,repoNames[0][1])
        else:
            results.append(repoNames[0][1])

    if regLinkNames:
        results.append(regLinkNames[0][1])

    return results

def getGrantNumber(number):
    """Check if number is a grant number

    Use regular expressions to identify grant number

    Args:
        number (str): A potential candidate for a grant number

    Returns:
        str: The return value is a string of the grant number found.
        Will return an empty string if a grant number was not found


    """
    # see if the potential grant number has at least a 5 digit number
    checker = re.findall('[\d]', number)
    if len(checker) < 5:
        return ''
    # extract the grant number
    if checker:
        number = re.findall('[\d\w/-]+', number)
        return number[0]
    return ''


def getGrants(text):
    """Extract the grant number in a given text

    Use regular expressions to identify grant number

    Args:
        text (str): A body of text that may have potential grant numbers

    Returns:
        [(str, str)]: The return value is an array of pairs.
        The first value is the agency, the second is the grant number.


    """
    # words that signify funding, leading to acknowledgement of grant numbers
    filter_words = ["funds", "grant", "sponsor", "funding", "funded"]
    all_sentences = sent_tokenize(text)

    # get sentences that have the filter_words
    sentences = []
    sentence_idx = 0
    for sentence in all_sentences:
    	sentence_lower = sentence.lower()
    	found = False
    	for word in filter_words:
    		if word in sentence_lower:
    			sentences.append(sentence)
    			found = True
    			break
    	if found:
    		break
    	sentence_idx+=1
    sentences = all_sentences[sentence_idx:]


    result = []
    grant_stack = []
    agency_stack = []

    # go through each sentence and look for the funding agency
    # if the funding agency is found, then look for the grant number
    for sentence in sentences:
    	words = re.split('\W+',sentence)
    	words = [word.replace('.', '') for word in words]
    	added = []
    	for i in range(0, len(words)):
    		if i in added:
    		    continue
    		word = words[i]
    		word_tokens = [word.lower()]
    		lookup_word = checkDict(word_tokens, my_tree_map)
    		if isinstance(lookup_word, str) and word not in stopwords:
    			longest_word = getLongestWord(words[i:], my_tree_map)
    			if longest_word[0]==0:
    				agency_stack.append((word, i))
    			else:
    				agency_stack.append((longest_word[1], i))
    			continue
    		number = getGrantNumber(word)
    		if number:
    		    grant_stack.append((number, i))
    		    continue
    		for j in range(i + 1, len(words)):
    			word += " " + words[j]
    			word_tokens.append(words[j].lower())
    			lookup_word = checkDict(word_tokens, my_tree_map)
    			if isinstance(lookup_word, str):
    				added += range(i, j + 1)
    				agency_stack.append((word, j))
    				break

        # find agency that is closest to the grant number
    	threshold = 4
    	if grant_stack:
    	    for grant, grant_index in grant_stack:
    	        best_agency = None
    	        minimum = 100000
    	        for agency, agency_index in agency_stack:
    	            if abs(grant_index - agency_index) < minimum:
    	                minimum = abs(grant_index - agency_index)
    	                best_agency = agency
    	        if minimum > threshold or best_agency is None:
    	            result.append(("Agency not found", grant))
    	            continue
    	        result.append((best_agency, grant))
    	elif agency_stack:
    	    for agency, agency_index in agency_stack:
    	        result.append((agency, "Grant not found"))

    # filter out the invalid funding agency/grant combinations
    grantless_agencies = []
    for agency, grant in result:
        if grant is "Grant not found":
            grantless_agencies.append((agency, grant))
    result = [(agency, grant) for (agency, grant) in result if (agency, grant) not in grantless_agencies]
    result_agencies = [agency for (agency, grant) in result]
    for agency, grant in grantless_agencies:
        if agency not in result_agencies:
            result.append((agency, grant))

    return list(set(result))

def getTreeMap():
    return my_tree_map

def isWorkingLink(link):
    """Check if the link is broken

    Makes a HTTP request to the website to check if it exists

    Args:
        link (str): The link/url of the website

    Returns:
        bool: True if the link is working. False if it is broken


    """
    try:
    	r = requests.get(link, timeout=4)
    	if r.status_code==200 or r.status_code==302 or r.status_code==304:
    		return True
    except:
    	return False
    return False

def extractFromXML(filename, getAbstractOnly=True, xmlString='', incompletePub={}):
    """Extract all metadata from publication in the PMC XML format

    Using xml.ETree to parse the xml and extract relevant metadata

    Args:
        filename (str): The path to the xml file

    Returns:
        obj: The return value is an object containing all metadata


    """
    pub = incompletePub

    # check if file exists and is xml file
    root = None
    if xmlString:
        root = ET.fromstring(xmlString)

    if root is None and os.path.isfile(filename) and filename.endswith('.xml'):
    	tree = ET.parse(filename)
    	root = tree.getroot()

    if root is None:
        return pub

    text_node = None

    # get abstract or full paper
    if getAbstractOnly:
    	text_node = root.find("./article/front/article-meta/abstract")
    else:
        text_node = root.find("./article/body")

    if text_node is not None:
        # extract title
        if 'title' not in pub or not pub['title']:
            title_node = root.find("./article/front/article-meta/title-group/article-title")
            pub['title'] = ET.tostring(title_node, encoding='utf-8', method='text').decode('utf-8').strip()
        if 'journal' not in pub or not pub['journal']:
            journal_node = root.find("./article/front/journal-meta/journal-title")
            pub['journal'] = journal_node.text
    	# extract authors
        if 'authors' not in pub or not pub['authors']:
            authors_node = root.find("./article/front/article-meta/contrib-group")
            pub['authors'] = []
            for author in authors_node.iter('name'):
            	pub['authors'].append({'first_name': author.find('given-names').text, 'last_name':author.find('surname').text})

        # extract institutions:
        # TODO: needs improvement
        if 'institutions' not in pub or len(pub['institutions'])<2:
            affiliations = []
            aff_node = root.findall("./article/front/article-meta/aff")
            if not aff_node:
            	aff_node = root.findall("./article/front/article-meta/contrib-group/aff")
            for aff in aff_node:
                aff_xml = ET.tostring(aff, encoding='utf-8', method='xml').decode('utf-8')
                aff_xml = aff_xml[aff_xml.find('>')+1:aff_xml.rfind('<')]
                label_tag = ''
                if aff_xml.find('<sup>')>=0:
                	label_tag = 'sup'
                elif aff_xml.find('<label>')>=0:
                	label_tag = 'label'

            # remove superscript labels
            if label_tag:
            	for i in range(1, 20):
            		superscript_num = '<'+label_tag+'>'+str(i)+'</'+label_tag+'>'
            		find_aff = aff_xml.find(superscript_num)
            		if find_aff >= 0:
            			start_idx = find_aff+len(superscript_num)
            			end_idx = aff_xml.find('<'+label_tag+'>', start_idx)
            			institution = aff_xml[start_idx:end_idx].strip()
            			if institution.endswith(' and'):
            				institution = institution[:-4]
            			affiliations.append(institution)
            		else:
            			break
            else:
            	affiliations.append(aff_xml)
            # filter out institutions, only save ones that have certain keywords
            filtered_aff = []
            for aff in affiliations:
            	tokens = aff.split(',')
            	token_idx = 0
            	found_idx = 0
            	for token in tokens:
            		token_lower = token.lower()
            		if 'department' not in token_lower:
            			if 'univ' in token_lower or\
            			 'insti' in token_lower or\
            			  'school' in token_lower or \
            			  'college' in token_lower or \
            			  'lab' in token_lower or\
            			  'center' in token_lower:
            				found_idx = token_idx
            		token_idx+=1
            	filtered_aff.append(', '.join(tokens[found_idx:]))

            pub['institutions'] = filtered_aff
            pub['no_filter_inst'] = affiliations

        # extract tags
        if 'tags' not in pub or pub['tags']:
            pub['tags'] = []
            tag_node = root.findall("./article/front/article-meta/article-categories/subj-group/subj-group")
            for tag in tag_node:
            	pub['tags'].append(tag.find('subject').text)

        # extract PMID and DOI
        id_node = root.findall("./article/front/article-meta/article-id")
        for id in id_node:
        	if id.get('pub-id-type')=='pmid':
        		pub['pmid'] = id.text
        	elif id.get('pub-id-type')=='doi':
        		pub['doi'] = id.text
        	elif id.get('pub-id-type')=='pmc':
        		pub['pmc'] = id.text

        # extract pub-date
        date_node = root.findall("./article/front/article-meta/pub-date")
        for date in date_node:
        	try:
        			year = date.find('year')
        			year = int(year.text) if year is not None else 0
        			month = date.find('month')
        			month = int(month.text) if month is not None else 1
        			day = date.find('day')
        			day = int(day.text) if day is not None else 1

        			pub['date'] = datetime.datetime(year,month,day).strftime('%Y-%m-%dT%H:%M:%SZ')
        			if date.get('pub-type') in ['epub', 'pmc-release']:
        				break
        	except:
        		pub['date'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        		print(pub['pmid'], 'does not have fully formed date')

        # extract abstract
        if 'abstract' not in pub or pub['abstract']:
            abstract = ET.tostring(text_node, encoding='utf-8', method='text').decode('utf-8')
            pub['abstract'] = abstract.strip()


        # extract funding
        if 'funding' not in pub or not pub['funding']:
            pub['funding'] = []
            funding_node = root.findall("./article/back/ack/p")
            if funding_node:
            	funding_text = ''
            	for funding in funding_node:
            		funding_text +=' ' + ET.tostring(funding, encoding='utf-8', method='text').decode('utf-8')
            	pub['funding'] = getGrants(funding_text)

        # extract links
        if 'links' not in pub or not pub['links']:
            all_links = extractLinks(abstract, fileXML=root, searchFull=not getAbstractOnly)
            pub['links'] = [{'link':link[0], 'broken':False} for link in all_links[0]]
            pub['emails'] = all_links[1]
            for i in range(len(pub['links'])):
            	link = pub['links'][i]['link']
            	if not link.startswith('http'):
            		if not isWorkingLink('http://'+link):
            			pub['links'][i]['broken'] = True and not isWorkingLink('https://'+link)

        # extract the code repoLinks
        if not pub['repo']:
            lower_abstract = pub['abstract'].lower()
            repo = ''
            for word in REPO_FILTER_WORDS:
            	if word in lower_abstract:
            		repo = word
            		break
            pub['repo'] = repo

        pub['dateCreated'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        pub['dateUpdated'] = pub['dateCreated']

    return pub

def makeRequest(link):
    """Makes an HTTP request to the given link and retrieves content

    Uses pycurl to perform request

    Args:
        link (str): The link/url of the website

    Returns:
        str: The content that is returned from the website


    """
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, link)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()

    body = buffer.getvalue()
    # Body is a byte string.
    # We have to know the encoding in order to print it to a text file
    # such as standard output.
    return body.decode('iso-8859-1')

def getPubMedXML(pmid):
    """Makes an HTTP request to retrieve the XML for the given PMID

    Args:
        pmid (str/int): The Pubmed ID for the article

    Returns:
        str: The content that is returned from Pubmed


    """
    link = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&format=xml&id='+str(pmid)
    r_text = makeRequest(link)
    return r_text

def getPMCXML(pmcid):
    """Makes an HTTP request to retrieve the XML for the given PMC (Pubmed Central) ID

    Args:
        pmcid (str/int): The PMC ID for the article

    Returns:
        str: The content that is returned from PMC


    """
    link = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&format=xml&id='+str(pmcid)
    r_text = makeRequest(link)
    return r_text

def extractFromPubmed(pmid, doi=None, pmc=None):
    """Extract all metadata from publication in the Pubmed XML format

    Using xml.ETree to parse the xml and extract relevant metadata

    Args:
        pmid (str): The pubmed id of the publication
        doi (str, optional): The DOI of the publication. Default is None.
        pmc (str, optional): The PMC id of the publication. Default is None.

    Returns:
        obj: The return value is an object containing all metadata


    """
    pub = {}

    random_int = int(random.random()*10000)
    if doi:
        link = 'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=my_tool&email=my_email'+str(random_int)+'@example.com&format=json&ids='+str(doi)
    elif pmc:
        if not pmc.lower().startswith('pmc'):
            pmc = 'pmc'+pmc
        link = 'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=my_tool&email=my_email'+str(random_int)+'@example.com&format=json&ids='+str(pmc)

    r_text = makeRequest(link)
    json_body = json.loads(r_text)


    if 'records' in json_body and 'pmc' in json_body['records'][0]:
        pmc = json_body['records'][0]['pmcid']
    if 'records' in json_body and 'pmid' in json_body['records'][0]:
        pmid = json_body['records'][0]['pmid']
    else:
        link = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&format=json&term='+(doi or pmc)
        r_text = makeRequest(link)
        json_body = json.loads(r_text)
        if int(json_body['esearchresult']['count'])>0:
            pmid = json_body['esearchresult']['idlist'][0]
        else:
            return pub

    link = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&format=xml&id='+str(pmid)
    r_text = makeRequest(link)
    root = ET.fromstring(r_text)

    # get abstract
    text_node = root.find("./PubmedArticle/MedlineCitation/Article/Abstract")
    if text_node is not None:
        # extract title
        title_node = root.find("./PubmedArticle/MedlineCitation/Article/ArticleTitle")
        title = ET.tostring(title_node, encoding='utf-8', method='text').decode('utf-8').strip()
        journal_node = root.find("./PubmedArticle/MedlineCitation/Article/Journal/ISOAbbreviation")
        journal = journal_node.text
    	# extract authors
        authors_node = root.findall("./PubmedArticle/MedlineCitation/Article/AuthorList/Author")
        authors = []
        affiliations = []
        for author_node in authors_node:
        	if author_node.get('ValidYN')=='Y':
        		lastname = author_node.find('LastName')
        		if lastname is not None:
        			lastname = lastname.text
        			firstname = author_node.find('ForeName')
        			if firstname is not None:
        				firstname = firstname.text
        				initial = author_node.find('Initials')
        				if initial is not None:
        					firstname+=' '+initial.text
        				authors.append({'first_name': firstname, 'last_name':lastname})

        		# extract institutions
        		affilation_node = author_node.find('AffiliationInfo/Affiliation')
        		if affilation_node is not None:
        			affiliations.append(affilation_node.text)




        # filter out institutions, only save ones that have certain keywords
        filtered_aff = []
        for aff in affiliations:
        	tokens = aff.split(',')
        	token_idx = 0
        	found_idx = 0
        	for token in tokens:
        		token_lower = token.lower()
        		if 'department' not in token_lower:
        			if 'univ' in token_lower or\
        			 'insti' in token_lower or\
        			  'school' in token_lower or \
        			  'college' in token_lower or \
        			  'lab' in token_lower or\
        			  'center' in token_lower:
        				found_idx = token_idx
        		token_idx+=1
        	filtered_aff.append(', '.join(tokens[found_idx:]))

        # extract tags
        tags = []
        tag_node = root.findall("./PubmedArticle/MedlineCitation/MeshHeadingList/MeshHeading")
        for tag in tag_node:
        	tags.append(tag.find('DescriptorName').text)

        # extract PMID and DOI
        id_node = root.findall("./PubmedArticle/PubmedData/ArticleIdList/ArticleId")
        for id in id_node:
        	if id.get('IdType')=='pubmed':
        		pub['pmid'] = id.text
        	elif id.get('IdType')=='doi':
        		pub['doi'] = id.text
        	elif id.get('IdType')=='pmc':
        		pub['pmc'] = id.text

        # extract pub-date
        date_node = root.find("./PubmedArticle/MedlineCitation/DateCreated")
        if date_node:
        	year = date_node.find('Year')
        	year = int(year.text) if year is not None else 0
        	month = date_node.find('Month')
        	month = int(month.text) if month is not None else 1
        	day = date_node.find('Day')
        	day = int(day.text) if day is not None else 1
        	pub['date'] = datetime.datetime(year,month,day).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
        	pub['date'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        	print(pub['pmid'], 'does not have fully formed date')

        # extract abstract
        abstract = ET.tostring(text_node, encoding='utf-8', method='text').decode('utf-8')
        abstract = abstract.strip()
        lower_abstract = abstract.lower()


        # extract funding
        funding = []
        funding_node = root.findall("./PubmedArticle/MedlineCitation/Article/GrantList/Grant")
        if funding_node:
            for fund in funding_node:
                agencies = set()
                agency = fund.find('Agency').text
                agencies_tokens = agency.split()
                i = 0
                num_agencies = len(agencies_tokens)
                while i < num_agencies:
                    potential_agency = getLongestWord(agencies_tokens[i:], my_tree_map)
                    agencies.add(" ".join(agencies_tokens[i:i+potential_agency[0]+1]))
                    i+=potential_agency[0]
                    i+=1
                grant = fund.find('GrantID')
                if grant is not None:
                    grant = grant.text
                else:
                    grant = 'Grant not found'

                for agency in agencies:
                    if agency:
                        funding.append((agency, grant))

        # extract links
        all_links = extractLinks(abstract)


        links = [{'link':link[0], 'broken':False} for link in all_links[0]]
        emails = all_links[1]
        for i in range(len(links)):
            link = links[i]['link']

            if link.endswith('Supplementary'):
                link = link[:link.rfind('Supplementary')]
            elif link.endswith('Contact'):
                link = link[:link.rfind('Contact')]

            links[i]['link'] = link
            if not link.startswith('http'):
            	if not isWorkingLink('http://'+link):
            		links[i]['broken'] = True and not isWorkingLink('https://'+link)

        # extract the code repoLinks
        repo = ''
        for word in REPO_FILTER_WORDS:
        	if word in lower_abstract:
        		repo = word
        		break

        foundRepo = False
        if not repo:
        	for word in REPO_FILTER_WORDS:
        		for link in all_links[0]:
        			if word in link[0]:
        				repo = word
        				foundRepo = True
        				break
        		if foundRepo:
        			break



        pub['title'] = title
        pub['abstract'] = abstract
        pub['journal'] = journal
        pub['repo'] = repo
        pub['authors'] = authors
        pub['institutions'] = filtered_aff
        pub['no_filter_inst'] = affiliations
        pub['tags'] = tags
        pub['links'] = links
        pub['emails'] = emails
        pub['funding'] = funding
        pub['dateCreated'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        pub['dateUpdated'] = pub['dateCreated']

        if pmc and (not pub['links'] or not pub['tags'] or not pub['funding'] or len(pub['institutions'])<2):
            pmc_link = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&format=xml&id='+pmc
            r_text = makeRequest(pmc_link)
            print('retrieving full paper')
            pub = extractFromXML('', xmlString=r_text, incompletePub=pub)

    return pub
# title='A system for generating transcription regulatory networks with combinatorial control of transcription'
# repo = 'github'
# abstract = 'abra.com/kadabra, github.com/tool/toolbox'
# tree = ET.parse('../bioinformatics/has_repo/2373921.xml')
# root = tree.getroot()
# links = extractLinks(title, root, searchFull=True)
# name = extractName(title, abstract)
# print(links)
# print(name)
# pub = extractFromXML('../bioinformatics/has_repo/2373921.xml')
# print(json.dumps(pub, indent=2))
