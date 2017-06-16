from nltk.corpus import stopwords
from nltk.stem.wordnet import WordNetLemmatizer
import string, os, re, json, threading, gensim
import xml.etree.ElementTree as ET
from gensim import corpora
from scrape import getPMCXML
import config.config as CONFIG


stop = set(stopwords.words('english'))
exclude = set(string.punctuation)
lemma = WordNetLemmatizer()

docs = []
dictionary = {}

def clean(doc):
    stop_free = " ".join([i for i in doc.lower().split() if i not in stop])
    punc_free = ''.join(ch for ch in stop_free if ch not in exclude)
    normalized = " ".join(lemma.lemmatize(word) for word in punc_free.split())
    return normalized


class pubThread(threading.Thread):
    def __init__(self, threadID, pmcids):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.pmcids = pmcids

    def run(self):
        print('Starting thread', self.threadID)
        global docs

        for pmcid in self.pmcids:
            raw_text = getPMCXML(pmcid)

            root = ET.fromstring(raw_text)
            if root:
                abstract_node = root.find("./article/front/article-meta/abstract")

                if abstract_node:
                    abstract_text = ET.tostring(abstract_node, encoding='utf-8', method='text').decode('utf-8')
                    docs.append({'abstract': abstract_text})

def getAbstracts():
    if os.path.exists('./lda/abstracts.json'):
        global docs
        with open('./lda/abstracts.json', 'r') as f:
            docs = json.load(f)
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
        with open('./abstracts.json', 'w') as f:
            json.dump(docs, f)

def getDictionary(getMatrix=False):
    global dictionary
    doc_clean = []

    if getMatrix:
        getAbstracts()
        doc_clean = [clean(doc['abstract']).split() for doc in docs]

    if os.path.exists('./lda/abstract.dict'):
        # with open('./abstract.dict', 'r') as f:
        dictionary = corpora.Dictionary.load('./lda/abstract.dict')
    else:
        dictionary = corpora.Dictionary(doc_clean)
        dictionary.save('./lda/abstract.dict')

    return [dictionary.doc2bow(doc) for doc in doc_clean]

def generateLDAModel():

    doc_term_matrix = getDictionary(getMatrix=True)

    Lda = gensim.models.ldamodel.LdaModel
    ldamodel = Lda(doc_term_matrix, num_topics=20, id2word=dictionary, alpha='auto', passes=50)
    ldamodel.save('./lda/lda.model')

    return ldamodel

def main():
    ldamodel = None
    if os.path.exists('./lda/lda.model'):
        ldamodel = gensim.models.ldamodel.LdaModel.load('./lda/lda.model')
    else:
        ldamodel = generateLDAModel()

    data = 'protein protein interaction'
    getDictionary()
    word_vec = dictionary.doc2bow(data.split())
    a = list(sorted(ldamodel[word_vec], key=lambda x: x[1]))
    print(ldamodel.print_topic(a[-1][0], topn=20), a[-1])
    print(ldamodel.print_topic(a[-2][0], topn=20), a[-2])
    # topics = ldamodel.print_topics(num_topics=20, num_words=10)
    # for topic in topics:
    #     print(topic)
    #     print()
if __name__ == '__main__':
    main()
