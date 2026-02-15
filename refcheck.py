import React, { useState } from 'react';
import { 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Search, 
  ExternalLink, 
  Trash2, 
  Copy, 
  BookOpen, 
  Loader2,
  FileText,
  Globe,
  Database
} from 'lucide-react';

const App = () => {
  const [inputText, setInputText] = useState('');
  const [results, setResults] = useState([]);
  const [isChecking, setIsChecking] = useState(false);
  const [progress, setProgress] = useState(0);

  // 清理引用文本
  const cleanCitation = (text) => {
    // 移除 [1], 1., (1) 等常见序号
    return text.replace(/^\[\d+\]\s*/, '')
               .replace(/^\d+\.\s*/, '')
               .replace(/^\(\d+\)\s*/, '')
               .trim();
  };

  /**
   * 改进的相似度检查算法：关键词覆盖率
   * @param {string} userQuery - 用户输入的整行引用
   * @param {string} apiTitle - API 返回的标准标题
   */
  const checkSimilarity = (userQuery, apiTitle) => {
    if (!apiTitle || !userQuery) return false;

    // 1. 预处理：转小写，移除标点，仅保留字母数字和中文
    const normalize = (str) => str.toLowerCase().replace(/[^\w\u4e00-\u9fa5\s]/g, ' ');
    
    const normQuery = normalize(userQuery);
    const normTitle = normalize(apiTitle);

    // 2. 提取标题中的有效关键词（忽略小于3个字符的短词，除非是中文）
    const titleWords = normTitle.split(/\s+/).filter(w => 
      (w.length > 2 && /^[a-zA-Z0-9]+$/.test(w)) || /[\u4e00-\u9fa5]/.test(w)
    );

    if (titleWords.length === 0) return false;

    // 3. 检查标题关键词在用户查询中出现的比例
    let matchCount = 0;
    titleWords.forEach(word => {
      if (normQuery.includes(word)) {
        matchCount++;
      }
    });

    const coverage = matchCount / titleWords.length;

    // 4. 判定标准：
    // - 如果关键词覆盖率超过 60%，视为匹配
    // - 或者如果标题本身就是查询的子串（短标题情况）
    return coverage > 0.6 || normQuery.includes(normTitle);
  };

  // OpenAlex API
  const checkOpenAlex = async (query) => {
    try {
      const res = await fetch(`https://api.openalex.org/works?search=${encodeURIComponent(query)}&per-page=1`);
      if (!res.ok) throw new Error('API Error');
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        const item = data.results[0];
        const isMatch = checkSimilarity(query, item.display_name);
        return {
          found: true,
          match: isMatch,
          title: item.display_name,
          year: item.publication_year,
          url: item.doi,
          sourceName: 'OpenAlex'
        };
      }
      return { found: false, sourceName: 'OpenAlex' };
    } catch (e) {
      return { error: true, sourceName: 'OpenAlex' };
    }
  };

  // CrossRef API (替代 Semantic Scholar)
  const checkCrossRef = async (query) => {
    try {
      // CrossRef 的 bibliographic 查询非常适合这种非结构化引用
      const res = await fetch(`https://api.crossref.org/works?query.bibliographic=${encodeURIComponent(query)}&rows=1`);
      if (!res.ok) throw new Error('API Error');
      const data = await res.json();
      
      if (data.message && data.message.items && data.message.items.length > 0) {
        const item = data.message.items[0];
        // CrossRef 标题可能是数组
        const title = item.title ? item.title[0] : '';
        const year = item.created ? item.created['date-parts'][0][0] : '';
        const isMatch = checkSimilarity(query, title);
        
        return {
          found: true,
          match: isMatch,
          title: title,
          year: year,
          url: item.URL, // CrossRef 通常直接返回 DOI URL
          sourceName: 'CrossRef'
        };
      }
      return { found: false, sourceName: 'CrossRef' };
    } catch (e) {
      return { error: true, sourceName: 'CrossRef' };
    }
  };

  const checkReferences = async () => {
    if (!inputText.trim()) return;

    setIsChecking(true);
    setResults([]);
    setProgress(0);

    const lines = inputText.split('\n').filter(line => line.trim() !== '');
    const total = lines.length;
    let processed = 0;
    const newResults = [];

    for (const line of lines) {
      const query = cleanCitation(line);
      
      // 并行请求 OpenAlex 和 CrossRef
      const [oaResult, crResult] = await Promise.all([
        checkOpenAlex(query),
        checkCrossRef(query)
      ]);

      // 综合判断状态
      let status = 'not_found';
      let message = '未找到匹配';
      
      // 只要有一个数据库判定为高度匹配(verified)，就算通过
      if (oaResult.match || crResult.match) {
        status = 'verified';
        message = '验证通过';
      } 
      // 如果两个都找到了但都不匹配
      else if (oaResult.found || crResult.found) {
        status = 'suspicious';
        message = '标题差异较大';
      }

      newResults.push({
        original: line,
        query: query,
        status: status,
        message: message,
        sources: {
          openAlex: oaResult,
          crossRef: crResult // 更改为 CrossRef
        }
      });

      processed++;
      setProgress(Math.round((processed / total) * 100));
      // 简单的速率限制
      await new Promise(r => setTimeout(r, 200));
    }

    setResults(newResults);
    setIsChecking(false);
  };

  const StatusBadge = ({ result }) => {
    if (result.error) return <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">连接失败</span>;
    if (!result.found) return <span className="text-xs text-red-500 bg-red-50 px-2 py-1 rounded">未收录</span>;
    if (result.match) return <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded border border-green-200">已验证</span>;
    return <span className="text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded border border-yellow-200">疑似</span>;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-600" />
            <h1 className="text-xl font-bold text-slate-800">
              RefCheck Pro <span className="text-xs font-normal text-slate-500 bg-slate-100 px-2 py-1 rounded-full ml-2">OpenAlex + CrossRef</span>
            </h1>
          </div>
          <div className="text-xs text-slate-500 hidden md:flex items-center gap-3">
             <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500"/> OpenAlex</span>
             <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-blue-500"/> CrossRef (DOI)</span>
             <span className="flex items-center gap-1"><Search className="w-3 h-3 text-orange-500"/> Google/百度</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Input Section */}
          <div className="lg:col-span-4 space-y-4">
            <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 h-full flex flex-col">
              <label className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                输入参考文献列表
              </label>
              
              <textarea
                className="flex-1 w-full p-4 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none resize-none min-h-[400px]"
                placeholder="[1] Vaswani, A. Attention Is All You Need. 2017.&#10;[2] 直接粘贴您的论文引用列表..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={isChecking}
              />

              <div className="mt-4 pt-4 border-t border-slate-100">
                <button
                  onClick={checkReferences}
                  disabled={isChecking || !inputText.trim()}
                  className={`w-full py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-bold text-white transition-all shadow-md ${
                    isChecking ? 'bg-indigo-400 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg'
                  }`}
                >
                  {isChecking ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      多库检索中 {progress}%
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      开始全面核对
                    </>
                  )}
                </button>
                <p className="text-xs text-center text-slate-400 mt-2">
                  双重校验：OpenAlex + CrossRef (DOI库)
                </p>
              </div>
            </div>
          </div>

          {/* Results Section */}
          <div className="lg:col-span-8">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 min-h-[500px] flex flex-col">
              <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 rounded-t-xl">
                <h3 className="font-semibold text-slate-700">核对报告</h3>
                <div className="flex gap-2">
                  {results.length > 0 && !isChecking && (
                    <button 
                      onClick={() => {
                        const valid = results.filter(r => r.status === 'verified').map(r => r.original).join('\n');
                        navigator.clipboard.writeText(valid);
                        alert('已复制');
                      }}
                      className="text-xs bg-white border hover:bg-slate-50 px-3 py-1.5 rounded-md flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" /> 复制通过项
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {results.length === 0 && !isChecking && (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20 opacity-60">
                    <Database className="w-16 h-16 mb-4 stroke-1" />
                    <p>准备就绪，等待输入</p>
                  </div>
                )}

                {results.map((item, index) => (
                  <div key={index} className="border border-slate-200 rounded-lg p-4 hover:shadow-sm transition-shadow bg-white">
                    {/* Main Status Header */}
                    <div className="flex items-start gap-3 mb-3">
                      <div className="mt-1">
                        {item.status === 'verified' ? <CheckCircle className="w-5 h-5 text-green-500" /> :
                         item.status === 'suspicious' ? <AlertCircle className="w-5 h-5 text-yellow-500" /> :
                         <XCircle className="w-5 h-5 text-red-500" />}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-slate-800 font-medium leading-relaxed">{item.original}</p>
                        
                        {/* 状态提示文字 */}
                        {item.status === 'suspicious' && (
                          <p className="text-xs text-yellow-600 mt-1">
                            提示：数据库找到了相关文献，但标题关键词匹配度不足，请人工确认。
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Sources Grid */}
                    <div className="ml-8 grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                      {/* OpenAlex Result */}
                      <div className={`bg-slate-50 rounded p-2 text-xs border ${item.sources.openAlex.match ? 'border-green-200 bg-green-50' : 'border-slate-100'}`}>
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-semibold text-slate-500">OpenAlex</span>
                          <StatusBadge result={item.sources.openAlex} />
                        </div>
                        {item.sources.openAlex.title && (
                          <div className="text-slate-600 truncate" title={item.sources.openAlex.title}>
                            {item.sources.openAlex.title}
                          </div>
                        )}
                      </div>

                      {/* CrossRef Result (原 Semantic Scholar) */}
                      <div className={`bg-slate-50 rounded p-2 text-xs border ${item.sources.crossRef.match ? 'border-green-200 bg-green-50' : 'border-slate-100'}`}>
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-semibold text-slate-500">CrossRef (DOI)</span>
                          <StatusBadge result={item.sources.crossRef} />
                        </div>
                         {item.sources.crossRef.title && (
                          <div className="text-slate-600 truncate" title={item.sources.crossRef.title}>
                            {item.sources.crossRef.title}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* External Check Tools */}
                    <div className="ml-8 pt-2 border-t border-slate-100 flex flex-wrap gap-2 items-center">
                      <span className="text-xs text-slate-400 mr-1">人工复核工具:</span>
                      
                      <a 
                        href={`https://scholar.google.com/scholar?q=${encodeURIComponent(item.query)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-100 transition-colors"
                      >
                        <Search className="w-3 h-3" /> Google 学术
                      </a>

                      <a 
                        href={`https://xueshu.baidu.com/s?wd=${encodeURIComponent(item.query)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-100 transition-colors"
                      >
                        <Search className="w-3 h-3" /> 百度学术
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
