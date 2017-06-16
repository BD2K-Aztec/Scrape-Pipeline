import threading, os, re, json
from integrate import generateCompleteJSON, converToSolrFormat, pushToSolr, migrateOldEntries
from scrape import makeRequest
import config.config as CONFIG


all_entries = []

class pubThread(threading.Thread):
    def __init__(self, threadID, pmcids):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.pmcids = pmcids

    def run(self):
        print('Starting thread', self.threadID)
        for pmcid in self.pmcids:
            entry = generateCompleteJSON(pmc=pmcid, source='PMC Extraction')
            entry = converToSolrFormat(entry)
            all_entries.append(entry)

class migrateThread(threading.Thread):
    def __init__(self, threadID, entries):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.entries = entries

    def run(self):
        print('Starting thread', self.threadID)
        for entry in self.entries:
            try:
                new_entry = migrateOldEntries(entry)
                all_entries.append(new_entry)
            except:
                print(entry['id'])
                new_entry = migrateOldEntries(entry)
                all_entries.append(new_entry)


def genEntryUsingThreads(pmcids, numThreads=16):
    print('total publications:', len(pmcids))
    threads = []
    numEntriesPerThread = int(len(pmcids)/numThreads)
    remainder = len(pmcids)%numThreads
    startIdx = 0
    endIdx = numEntriesPerThread
    for i in range(numThreads):
        if i < remainder:
            endIdx+=1
        print(startIdx, endIdx, endIdx-startIdx)
        pmcid_arr = pmcids[startIdx:endIdx]
        t = pubThread(i, pmcid_arr)
        threads.append(t)
        t.start()

        startIdx = endIdx
        endIdx+=numEntriesPerThread

    for t in threads:
        t.join()


def insertNewEntries():

    using_dir = CONFIG.JOURNAL_DIRS

    filesInDir = []
    for directory in using_dir:
        filesInDir += [s for s in os.listdir(directory)]

    pmcids = []
    for f in filesInDir:
        pmc_regex = re.search('[\d]+', f)
        if pmc_regex:
            pmc = pmc_regex.group(0)
            pmcids.append(pmc)

    genEntryUsingThreads(pmcids)
    insertToSolr()

def insertToSolr():
    totalAdded = 0
    for entry in all_entries:
        # converted_entry = converToSolrFormat(entry)
        # print(converted_entry)
        status = pushToSolr(entry, checkCollisions=True, ignoreMissing=True)
    	# if not status:
    	# 	print(json.dumps(entry, indent=2))
        totalAdded+=status
    print(totalAdded, 'new entries added')

def migrateUsingThreads(entries, numThreads=16):
    print('total publications:', len(entries))
    threads = []
    numEntriesPerThread = int(len(entries)/numThreads)
    remainder = len(entries)%numThreads
    startIdx = 0
    endIdx = numEntriesPerThread
    for i in range(numThreads):
        if i < remainder:
            endIdx+=1
        print(startIdx, endIdx, endIdx-startIdx)
        entry_arr = entries[startIdx:endIdx]
        t = migrateThread(i, entry_arr)
        threads.append(t)
        t.start()

        startIdx = endIdx
        endIdx+=numEntriesPerThread

    for t in threads:
        t.join()

def migrate(rows=20000):
    link = CONFIG.OLD_SOLR_URL+'select?q=*%3A*&start=0&rows='+str(rows)+'&wt=json&indent=true'

    r_text = makeRequest(link)
    json_body = json.loads(r_text)
    print('migrating', json_body['response']['numFound'], 'entries')
    migrateUsingThreads(json_body['response']['docs'])

    insertToSolr()

def main():
    migrate()

if __name__ == '__main__':
    main()
