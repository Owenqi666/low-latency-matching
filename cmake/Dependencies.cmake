include(FetchContent)
FetchContent_Declare(boost
  URL https://archives.boost.io/release/1.89.0/source/boost_1_89_0.tar.bz2
  URL_HASH SHA256=85a33fa22621b4f314f8e85e1a5e2a9363d22e4f4992925d4bb3bc631b5a0c7a
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  # Only the mature header libraries are used; do not build all Boost libraries.
  SOURCE_SUBDIR llmatch-unused-build-directory
)
FetchContent_MakeAvailable(boost)
add_library(llmatch_boost INTERFACE)
target_include_directories(llmatch_boost SYSTEM INTERFACE ${boost_SOURCE_DIR})

if(BUILD_TESTING)
set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.17.0.tar.gz
  URL_HASH SHA256=65fab701d9829d38cb77c14acdc431d2108bfdbf8979e40eb8ae567edf10b27c
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(googletest)
endif()
