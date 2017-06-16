import threading, os, re, json
from nltk.tokenize import sent_tokenize, word_tokenize
from scrape import getPMCXML
import xml.etree.ElementTree as ET
from gensim.models import Word2Vec
import config.config as CONFIG

sentences = []

class pubThread(threading.Thread):
    def __init__(self, threadID, pmcids):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.pmcids = pmcids

    def run(self):
        print('Starting thread', self.threadID)
        for pmcid in self.pmcids:
            raw_text = getPMCXML(pmcid)

            root = ET.fromstring(raw_text)
            if root:
                abstract_node = root.find("./article/front/article-meta/abstract")
                fulltext_node = root.find("./article/body")

                if abstract_node:
                    abstract_text = ET.tostring(abstract_node, encoding='utf-8', method='text').decode('utf-8')
                    sentence = sent_tokenize(abstract_text.lower())
                    for s in sentence:
                        sentences.append(word_tokenize(s))

                if fulltext_node:
                    fulltext_text = ET.tostring(fulltext_node, encoding='utf-8', method='text').decode('utf-8')
                    sentence = sent_tokenize(fulltext_text.lower())
                    for s in sentence:
                        sentences.append(word_tokenize(s))
def main():
    w2v_papers = None
    if os.path.exists('./word2vec/paper.model'):
        w2v_papers = Word2Vec.load('./word2vec/paper.model')
    else:
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

        threads = []
        numThreads = 16
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


        w2v_papers = Word2Vec(sentences)
        w2v_papers.save('./word2vec/paper.model')
    print(w2v_papers.most_similar('c++', topn=10))

if __name__ == '__main__':
    main()
