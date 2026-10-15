/* Vaste publicatiekeuzes van openvertaling.nl. */
(function () {
    'use strict';
    const nt = new Set(["markus","johannes","handelingen","romeinen","1johannes","jakobus","openbaring","kolossenzen","galaten","efeziers","filippenzen","mattheus","lukas","1korinthiers","2korinthiers","1tessalonicensen","2tessalonicensen","1timotheus","2timotheus","titus","filemon","hebreeen","1petrus","2petrus","2johannes","3johannes","judas"]);
    const excluded = new Set(['henoch', 'jubileeen', '1meqabyan', '2meqabyan', '3meqabyan', '4baruch']);
    window.ReaderPolicy = Object.freeze({
        isNewTestament: book => nt.has(book),
        allowsBook: book => !!book && !excluded.has(book.id) && !book.ethiopic && book.testament !== 'ET',
    });
})();
