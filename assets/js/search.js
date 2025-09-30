(function () {
    function displaySearchResults(results, store, searchTerm) {
        var searchResults = document.getElementById('search-results');
        var searchStatus = document.getElementById('search-status');

        if (results.length) {
            searchStatus.innerHTML = '<p class="search-count">' + results.length + '개의 검색 결과를 찾았습니다.</p>';
            var appendString = '';

            for (var i = 0; i < results.length; i++) {
                var item = store[results[i].ref];
                var excerpt = item.content.substring(0, 200);

                // 검색어 하이라이트
                if (searchTerm) {
                    var regex = new RegExp('(' + searchTerm + ')', 'gi');
                    excerpt = excerpt.replace(regex, '<mark>$1</mark>');
                }

                appendString += '<li class="search-result-item">';
                appendString += '<a href="' + item.url + '" class="search-result-link">';
                appendString += '<h3 class="search-result-title">' + item.title + '</h3>';
                appendString += '<p class="search-result-excerpt">' + excerpt + '...</p>';
                if (item.category) {
                    appendString += '<span class="search-result-category">' + item.category + '</span>';
                }
                appendString += '</a></li>';
            }

            searchResults.innerHTML = appendString;
        } else if (searchTerm) {
            searchStatus.innerHTML = '<p class="search-no-results">검색 결과가 없습니다.</p>';
            searchResults.innerHTML = '<li class="no-results"><div class="no-results-content"><h3>검색 결과를 찾을 수 없습니다</h3><p>다른 키워드로 다시 검색해보세요.</p></div></li>';
        } else {
            searchStatus.innerHTML = '';
            searchResults.innerHTML = '';
        }
    }

    function getQueryVariable(variable) {
        var query = window.location.search.substring(1);
        var vars = query.split('&');

        for (var i = 0; i < vars.length; i++) {
            var pair = vars[i].split('=');

            if (pair[0] === variable) {
                return decodeURIComponent(pair[1].replace(/\+/g, '%20'));
            }
        }
    }

    function trimmerEnKo(token) {
        return token
            .replace(/^[^\w가-힣]+/, '')
            .replace(/[^\w가-힣]+$/, '');
    };

    // Initialize lunr index
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

    // Debug: Check if store is loaded
    console.log('Window store:', window.store);
    console.log('Store keys:', Object.keys(window.store || {}));

    // Add data to lunr index
    for (var key in window.store) {
        idx.add({
            'id': key,
            'title': window.store[key].title,
            'author': window.store[key].author,
            'category': window.store[key].category,
            'content': window.store[key].content
        });
    }

    function performSearch(searchTerm) {
        console.log('Searching for:', searchTerm);
        if (searchTerm && searchTerm.trim()) {
            var results = idx.search(searchTerm);
            console.log('Search results:', results);
            displaySearchResults(results, window.store, searchTerm);
        } else {
            displaySearchResults([], window.store, '');
        }
    }

    // Get initial search term from URL
    var searchTerm = getQueryVariable('query');
    var searchBox = document.getElementById('search-box');

    if (searchTerm) {
        searchBox.value = searchTerm;
        performSearch(searchTerm);
    }

    // Add real-time search functionality
    var searchTimeout;
    searchBox.addEventListener('input', function () {
        clearTimeout(searchTimeout);
        var query = this.value;

        searchTimeout = setTimeout(function () {
            performSearch(query);
            // Update URL without page reload
            if (query) {
                history.replaceState(null, null, '/search?query=' + encodeURIComponent(query));
            } else {
                history.replaceState(null, null, '/search');
            }
        }, 300);
    });

    // Handle form submission
    document.querySelector('.search-form').addEventListener('submit', function (e) {
        e.preventDefault();
        var query = searchBox.value;
        performSearch(query);
        if (query) {
            history.pushState(null, null, '/search?query=' + encodeURIComponent(query));
        }
    });
})();