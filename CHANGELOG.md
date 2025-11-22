# Changelog

## [0.6.0](https://github.com/itsmaxymoo/photoserv/compare/0.5.1...0.6.0) (2025-11-22)


### Features

* Common entity base ([045e82e](https://github.com/itsmaxymoo/photoserv/commit/045e82e1189c7a8c4c06e72a125e472ef5ccd948))
* Return individual picture size information in the public API ([d02d2c9](https://github.com/itsmaxymoo/photoserv/commit/d02d2c9d84386babc537e7186da4047bc0d8925a))

## [0.5.1](https://github.com/itsmaxymoo/photoserv/compare/0.5.0...0.5.1) (2025-10-15)


### Bug Fixes

* 404 error when merging tags ([8c4d037](https://github.com/itsmaxymoo/photoserv/commit/8c4d037d1ee97702c686389652c5dde605eda032))

## [0.5.0](https://github.com/itsmaxymoo/photoserv/compare/0.4.2...0.5.0) (2025-10-10)


### Features

* Consistency checker ([02b983f](https://github.com/itsmaxymoo/photoserv/commit/02b983f64606135471e69b5ef559bc74a9ae10cc))


### Bug Fixes

* Photo sizes not deleted when photo deleted ([aad5770](https://github.com/itsmaxymoo/photoserv/commit/aad5770920273f20deea2da7d8e14c11e11a804b))

## [0.4.2](https://github.com/itsmaxymoo/photoserv/compare/0.4.1...0.4.2) (2025-10-08)


### Bug Fixes

* Album trying to access invalid Photo property ([656f6ff](https://github.com/itsmaxymoo/photoserv/commit/656f6ffbe08f1c669e56b4f7611b3160403b2fa7))
* Styles not persisting from dev to container context ([0ed68c4](https://github.com/itsmaxymoo/photoserv/commit/0ed68c4510c305c1745805855b4bedfb40c975e8))

## [0.4.1](https://github.com/itsmaxymoo/photoserv/compare/0.4.0...0.4.1) (2025-10-08)


### Bug Fixes

* Display images on album order page ([a70fbe6](https://github.com/itsmaxymoo/photoserv/commit/a70fbe6b9586ec4328eb644ccb4e20d3a6e712e9))
* Various styling issues ([50f61aa](https://github.com/itsmaxymoo/photoserv/commit/50f61aacc9e9d2b055f72a8b8d0bf1fe7c33df89))

## [0.4.0](https://github.com/itsmaxymoo/photoserv/compare/0.3.0...0.4.0) (2025-10-06)


### Features

* Better documentation ([5503424](https://github.com/itsmaxymoo/photoserv/commit/550342439bd485bf416f3a108f6fcea949fdd771))
* Create multiple photos at once ([3407f91](https://github.com/itsmaxymoo/photoserv/commit/3407f918cd962d30e43435bd3de5d251c2e1a9eb))
* Jobs overview ([d208deb](https://github.com/itsmaxymoo/photoserv/commit/d208debe805a00df7e4a56881c6f645a6e0ecefa))


### Bug Fixes

* All images falsely displayed as not public ([be5b6e8](https://github.com/itsmaxymoo/photoserv/commit/be5b6e8778f72a4ba5c8fc58f35b7d36c08acacc))
* Borders and styling missing for some form elements ([e6a7e30](https://github.com/itsmaxymoo/photoserv/commit/e6a7e302464610d543331b661788de3627559b35))
* Make sure all core tasks return a message ([3de33e5](https://github.com/itsmaxymoo/photoserv/commit/3de33e5d7822f18dd7c3adf30651dc4c5a3b92fb))
* Pagination no longer scrolls away when tables overflow horizontally ([997a5d5](https://github.com/itsmaxymoo/photoserv/commit/997a5d5bc4f4ba652021af4345a8e116d4223a88))

## [0.3.0](https://github.com/itsmaxymoo/photoserv/compare/0.2.0...0.3.0) (2025-09-30)


### Features

* Add Swagger based API explorer. ([7b92879](https://github.com/itsmaxymoo/photoserv/commit/7b92879b6f3d7780d4e172f22c8cf6b0ca44ec3a))

## [0.2.0](https://github.com/itsmaxymoo/photoserv/compare/0.1.7...0.2.0) (2025-09-26)


### Features

* Add mechanism to hide photos from the public API ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))
* Add support for album parent-child relationship ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))
* Use Postgres 18 by default ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))


### Bug Fixes

* Add /api/health endpoint ([21b0f50](https://github.com/itsmaxymoo/photoserv/commit/21b0f5017d1290fafb1dae8d89c8f4a48551cee7))
* Better EV display in UI ([156e9c0](https://github.com/itsmaxymoo/photoserv/commit/156e9c06704d260219bdfbe3e74d883c677dfb6e))
* Postgres health check throwing root user error ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))

## [0.1.7](https://github.com/itsmaxymoo/photoserv/compare/0.1.6...0.1.7) (2025-09-22)


### Bug Fixes

* DIsplay the status of size generation on the photo detail page ([72a4b06](https://github.com/itsmaxymoo/photoserv/commit/72a4b0652e93e89cc3cc97a645df25625519761c))
* Make layout better on mobile devices ([72a4b06](https://github.com/itsmaxymoo/photoserv/commit/72a4b0652e93e89cc3cc97a645df25625519761c))

## [0.1.6](https://github.com/itsmaxymoo/photoserv/compare/0.1.5...0.1.6) (2025-09-14)


### Bug Fixes

* Add timezone support ([a070dd7](https://github.com/itsmaxymoo/photoserv/commit/a070dd783075e734af324d251303f79f3c262211))
* Increase the default resolution of built-in sizes. ([88ddd0c](https://github.com/itsmaxymoo/photoserv/commit/88ddd0cb70c229c1d0ccec84212bb766ac849cfa))

## [0.1.5](https://github.com/itsmaxymoo/photoserv/compare/0.1.4...0.1.5) (2025-09-13)


### Bug Fixes

* Document OIDC callback URL ([58aaa04](https://github.com/itsmaxymoo/photoserv/commit/58aaa040a1300ffd4a515804e2818211225ca517))
* retrieve EV comp as float ([aba6c48](https://github.com/itsmaxymoo/photoserv/commit/aba6c481703c26221ca08317182d284624c22a40))

## [0.1.4](https://github.com/itsmaxymoo/photoserv/compare/0.1.3...0.1.4) (2025-09-13)


### Bug Fixes

* Run migrations in docker container ([5803676](https://github.com/itsmaxymoo/photoserv/commit/5803676facfa3266dbbb3884111dce6f5e3c42f0))

## [0.1.3](https://github.com/itsmaxymoo/photoserv/compare/v0.1.2...0.1.3) (2025-09-13)


### Bug Fixes

* add manifest ([b0d5d93](https://github.com/itsmaxymoo/photoserv/commit/b0d5d9378993068096d00180704fdd1ea37d5810))
* remove release type from actions def ([384fd08](https://github.com/itsmaxymoo/photoserv/commit/384fd08fcaa2bd9d0bac4499535b69b9a1c8a8be))

## [0.1.2](https://github.com/itsmaxymoo/photoserv/compare/v0.1.1...v0.1.2) (2025-09-13)


### Bug Fixes

* Configure release please (file) ([c1f8b7f](https://github.com/itsmaxymoo/photoserv/commit/c1f8b7ffba83844216e372a1c1e067787751421a))

## [0.1.1](https://github.com/itsmaxymoo/photoserv/compare/v0.1.0...v0.1.1) (2025-09-13)


### Bug Fixes

* Actions: switch to new googleapis namespace ([2d40bd3](https://github.com/itsmaxymoo/photoserv/commit/2d40bd3e40251e147a4d4c3651617382f109ced6))
* Do not include v in image tag ([fcbe002](https://github.com/itsmaxymoo/photoserv/commit/fcbe00288ddc8883b2e730bf27dc9340debc3fd0))

## 0.1.0 (2025-09-13)


### Bug Fixes

* Add documentation; example docker compose file ([10efc08](https://github.com/itsmaxymoo/photoserv/commit/10efc08f2bc8c916c1507fc89920ef296d5ddcef))
