import os, json, re

def createTreeMap(filename, cached_file='./utilities/cached_tree_map.json'):
	"""Generate a tree map data-structure to map phrases that have similar words
	This data structure allows you to parse through text to determine if
	a string of words is in the tree map. For example, if the tree map contains
	all universities, then parsing the text will give you the universities found
	in the text.
	Example TreeMap:
	{
		'university':{
						'of': {
								'california':{
												'san':{
													   'diego':{'$value': 'University of California, San Diego'},
													   'francisco':{'$value': 'University of California, San Francisco'}
													  },
												'berkeley': {'$value': 'University of California, Berkeley'}
											  },
								 'pennsylvania': {'$value': 'University of Pennsylvania'}
								}
						}
	 }


    Generates a treemap given a file containing the phrases and its synonyms (aliases).
	If a cached_file is given, it will load the treemap from the file.

    Args:
        filename (str): The path to the file that contains a json file with this format:
						[
							{
								'name': 'phrase1',
								'aliases': ['alias1', 'alias2']
							},...
						]
        cached_file (str, optional): The path to the file of the cached file.
		Default is './utilities/cached_tree_map.json'.

    Returns:
        dict: The return value is a dictionary of nested dictionaries.


    """
	my_tree_map = {}
	# load cached tree map
	if os.path.isfile(cached_file):
		with open(cached_file, 'r') as f:
			my_tree_map = json.load(f)
	else:
		# process entries in input file
		with open(filename) as f:
			data = json.load(f)
			for entry in data:

				inst_lower = entry['name'].lower()
				filter_name = inst_lower.replace(',', '')
				word_tokens = filter_name.split()
				my_tree_map = createDict(my_tree_map, word_tokens, entry['name'])

				for alias in entry['aliases']:
					# filter, make all lowercase, get rid of commas, dashes
					alias_lower = alias.lower()
					filter_name = re.sub('[-–]', ' ', alias_lower)
					filter_name = filter_name.replace(',', '')
					word_tokens = filter_name.split()

					my_tree_map = createDict(my_tree_map, word_tokens, entry['name'])
			# write to file, save tree map
			with open(cached_file, 'w') as map_file:
				json.dump(my_tree_map, map_file)

	return my_tree_map


def createDict(given_dict, words, value):
	"""Generate a nested dictionary given a list of words. It will add your words to
	the given_dict and return the new object.
	Example:
		given_dict:
			{
				'university':{
								'of': {
										'california':{
														'san':{
															   'diego':{'$value': 'University of California, San Diego'}
															  },
														'berkeley': {'$value': 'University of California, Berkeley'}
													  },
										 'pennsylvania': {'$value': 'University of Pennsylvania'}
										}
								}
			 }
		words: ['university', 'of', 'california', 'san', 'francisco']
		value: 'University of California, San Francisco'
		returns:
			{
				'university':{
								'of': {
										'california':{
														'san':{
															   'diego':{'$value': 'University of California, San Diego'},
															   'francisco':{'$value': 'University of California, San Francisco'}
															  },
														'berkeley': {'$value': 'University of California, Berkeley'}
													  },
										 'pennsylvania': {'$value': 'University of Pennsylvania'}
										}
								}
			 }

    Args:
        given_dict (dict): The dictionary that you would like to add your words to
        words ([str]): An array of words that you would like to add.
        value (str): The final string value that you would like your 'words' to represent.

    Returns:
        dict: The return value is the given_dict with the words added to it.


    """
	result_dict = given_dict
	# base case: if list is empty, add the value to the dict
	if not words:
		if '$value' in result_dict:
			result_dict['$value'].append(value)
		else:
			result_dict['$value'] = [value]
	else:
		# if the first word is already in dict, traverse through treemap with that word
		# call createDict with the tail of the words list
		if words[0] in result_dict:
			result_dict[words[0]] = createDict(result_dict[words[0]], words[1:], value)
		else:
			# if the first word is not in the dict, create a new path
			# call createDict with the tail of the words list
			result_dict[words[0]] = createDict({}, words[1:], value)

	return result_dict

def checkDict(words, given_dict):
	"""Check if a list of words is in the dict. If it is, return the value of the word.
	Otherwise, returns None



    Args:
        words ([str]): A list of words that you would like to look up
        given_dict (dict): The dictionary used to look up the words

    Returns:
        str: The return value is the final value of the words. If not found, returns None.


    """
	count = 0
	for word in words:
		if word in given_dict:
			given_dict = given_dict[word]
		else:
			return None

	if '$value' in given_dict:
		return given_dict['$value'][0]

	return given_dict

def getFirstValue(given_dict):
	if '$value' in given_dict:
		return given_dict['$value'][0]
	first_value = list(given_dict.keys())[0]
	return getFirstValue(given_dict[first_value])

def getLongestWord(words, tree_map):
	"""Given a list of words, returns the longest word (in terms of depth of the tree)


    Args:
        pmid (str): The pubmed id of the publication
        doi (str, optional): The DOI of the publication. Default is None.
        pmc (str, optional): The PMC id of the publication. Default is None.

    Returns:
        (str, int): The first value is the final value of the longest word (string).
		The second value is the number of words that matched in the given list of words.
		range: [0, len(words))

    """
	if not words:
		return None

	word_list = []
	longest_word = None
	counter = 0
	found_ctr = 0
	for word in words:
		word_list.append(word.lower())
		found_result = checkDict(word_list, tree_map)
		if isinstance(found_result, str):
			longest_word = found_result
			found_ctr = counter
		counter+=1

	return (found_ctr, longest_word)
