from io import BytesIO
import pycurl, json, sys, re

query_link = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql?format=json&query=SELECT%20?itemLabel%20?item%20?itemAltLabel%20WHERE%20{%20{%20?item%20wdt:P31%20wd:Q31855.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q3918.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q189004.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q902104.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q875538.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q43229.%20}%20UNION%20{%20?item%20wdt:P31%20wd:Q494230.%20}%20SERVICE%20wikibase:label%20{%20bd:serviceParam%20wikibase:language%20%22en%22.%20}%20}';

'''
SELECT ?itemLabel ?item ?itemAltLabel WHERE {
  { ?item wdt:P31 wd:Q31855. }
  UNION
  { ?item wdt:P31 wd:Q3918. }
  UNION
  { ?item wdt:P31 wd:Q189004. }
  UNION
  { ?item wdt:P31 wd:Q902104. }
  UNION
  { ?item wdt:P31 wd:Q875538. }
  UNION
  { ?item wdt:P31 wd:Q43229. }
  UNION
  { ?item wdt:P31 wd:Q494230. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
'''

def main():
    args = sys.argv
    output_filename = './utilities/inst_alias.json'
    if len(args)>1:
        output_filename = args[1]

    funding_file = None
    if len(args)==3:
        funding_file = args[2]

    new_list = []
    try:
        r_text = makeRequest(query_link)
        json_body = json.loads(r_text)

        inst_list = json_body['results']['bindings']
        for item in inst_list:
            name = item['itemLabel']['value']
            m = re.search('^Q[\d]{1,8}$', name)
            if m:
                continue
            institution = {'name': name}
            if 'itemAltLabel' in item:
                aliases_str = item['itemAltLabel']['value']
                institution['aliases'] = aliases_str.split(',')
            else:
                institution['aliases'] = []
            new_list.append(institution)
    except:
        print('Error')

    print('Processed', len(new_list), 'entries')
    if funding_file:
        with open(funding_file, 'r') as f:
            json_body = json.load(f)
            for item in json_body:
                new_list.append({'name': item['name'], 'aliases':item['aliases']})
        print('Added',len(json_body),'funding agencies')
    with open(output_filename, 'w') as outfile:
        json.dump(new_list, outfile)


def makeRequest(link):
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

if __name__ == '__main__':
    main()
