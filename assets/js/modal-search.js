(function() {
    // 모달이 열릴 때까지 기다리기
    function initModalSearch() {
        var modalSearchInput = document.getElementById('modal-search-input');
        var modalSearchButton = document.getElementById('modal-search-button');
        var modalSearchStatus = document.getElementById('modal-search-status');
        var modalSearchResults = document.getElementById('modal-search-results');
        
        if (!modalSearchInput || !window.store) {
            return;
        }

        // Lunr 인덱스 초기화
        function trimmerEnKo(token) {
            return token
                .replace(/^[^\w가-힣]+/, '')
                .replace(/[^\w가-힣]+$/, '');
        }

        var idx = lunr(function () {
            this.pipeline.reset();
            this.pipeline.add(
                trimmerEnKo,
                lunr.stopWordFilter,
                lunr.stemmer
            );
            this.field('id');
            this.field('title', { boost: 10 });
            this.field('author');
            this.field('category');
            this.field('content');
        });

        // 데이터를 lunr 인덱스에 추가
        for (var key in window.store) {
            idx.add({
                'id': key,
                'title': window.store[key].title,
                'author': window.store[key].author,
                'category': window.store[key].category,
                'content': window.store[key].content
            });
        }

        function displayModalResults(results, searchTerm) {
            if (results.length) {
                modalSearchStatus.innerHTML = '<p class="modal-search-count">' + results.length + '개의 검색 결과</p>';
                var appendString = '';

                // 최대 5개 결과만 표시
                var maxResults = Math.min(results.length, 5);
                for (var i = 0; i < maxResults; i++) {
                    var item = window.store[results[i].ref];
                    var excerpt = item.content.substring(0, 100);
                    
                    // 검색어 하이라이트
                    if (searchTerm) {
                        var regex = new RegExp('(' + searchTerm + ')', 'gi');
                        excerpt = excerpt.replace(regex, '<mark>$1</mark>');
                    }
                    
                    appendString += '<div class="modal-search-item">';
                    appendString += '<a href="' + item.url + '" class="modal-search-link-item">';
                    appendString += '<h4 class="modal-search-title">' + item.title + '</h4>';
                    appendString += '<p class="modal-search-excerpt">' + excerpt + '...</p>';
                    if (item.category) {
                        appendString += '<span class="modal-search-category">' + item.category + '</span>';
                    }
                    appendString += '</a></div>';
                }

                if (results.length > 5) {
                    appendString += '<div class="modal-search-more">';
                    appendString += '<a href="/search.html?query=' + encodeURIComponent(searchTerm) + '" class="modal-search-more-link">';
                    appendString += '더 많은 결과 보기 (' + (results.length - 5) + '개 더) →';
                    appendString += '</a></div>';
                }

                modalSearchResults.innerHTML = appendString;
                modalSearchResults.style.display = 'block';
            } else if (searchTerm) {
                modalSearchStatus.innerHTML = '<p class="modal-search-no-results">검색 결과가 없습니다</p>';
                modalSearchResults.innerHTML = '<div class="modal-no-results"><p>다른 키워드로 다시 검색해보세요.</p></div>';
                modalSearchResults.style.display = 'block';
            } else {
                modalSearchStatus.innerHTML = '';
                modalSearchResults.innerHTML = '';
                modalSearchResults.style.display = 'none';
            }
        }

        function performModalSearch(searchTerm) {
            if (searchTerm && searchTerm.trim()) {
                var results = idx.search(searchTerm);
                displayModalResults(results, searchTerm);
            } else {
                displayModalResults([], '');
            }
        }

        // 실시간 검색
        var searchTimeout;
        modalSearchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            var query = this.value;
            
            searchTimeout = setTimeout(function() {
                performModalSearch(query);
            }, 300);
        });

        // 엔터키 검색
        modalSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                var query = this.value.trim();
                if (query) {
                    // 검색 결과가 있으면 모달에서 보여주고, 없으면 검색 페이지로 이동
                    var results = idx.search(query);
                    if (results.length > 0) {
                        performModalSearch(query);
                    } else {
                        window.location.href = '/search.html?query=' + encodeURIComponent(query);
                    }
                }
            }
        });

        // 검색 버튼 클릭
        modalSearchButton.addEventListener('click', function() {
            var query = modalSearchInput.value.trim();
            if (query) {
                performModalSearch(query);
            }
        });

        // 모달이 열릴 때 입력창에 포커스
        var searchOverlay = document.getElementById('search');
        if (searchOverlay) {
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        if (searchOverlay.classList.contains('opened')) {
                            setTimeout(function() {
                                modalSearchInput.focus();
                            }, 100);
                        }
                    }
                });
            });
            observer.observe(searchOverlay, { attributes: true });
        }
    }

    // DOM이 로드된 후 초기화
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModalSearch);
    } else {
        initModalSearch();
    }

    // 모달이 열릴 때를 위한 추가 초기화
    setTimeout(initModalSearch, 1000);
})();