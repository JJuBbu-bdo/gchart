const { GoogleSpreadsheet } = require('google-spreadsheet');
const { JWT } = require('google-auth-library');
const gplay = require('google-play-scraper');

async function main() {
    // 1. 구글 인증 및 시트 연결
    const creds = JSON.parse(process.env.GCP_CREDENTIALS);
    const serviceAccountAuth = new JWT({
        email: creds.client_email,
        key: creds.private_key,
        scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });

    const sheetUrl = process.env.SHEET_URL;
    const docId = sheetUrl.match(/\/d\/([a-zA-Z0-9-_]+)/)[1];
    const doc = new GoogleSpreadsheet(docId, serviceAccountAuth);
    await doc.loadInfo();

    // 2. 한국 시간(KST) 기준으로 날짜 설정
    const now = new Date(new Date().getTime() + 9 * 60 * 60 * 1000);
    const todayStr = now.toISOString().split('T')[0];
    
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const yesterdayStr = yesterday.toISOString().split('T')[0];

    // 3. 어제 시트에서 전일 순위 파악
    const previousRanks = {};
    const yesterdaySheet = doc.sheetsByTitle[yesterdayStr];
    
    if (yesterdaySheet) {
        const rows = await yesterdaySheet.getRows();
        for (const row of rows) {
            const appName = row.get('앱 이름');
            const rank = row.get('순위');
            if (appName && rank) {
                previousRanks[appName] = parseInt(rank, 10);
            }
        }
    } else {
        console.log(`어제(${yesterdayStr}) 시트가 없어 전일 대비 데이터는 'NEW'로 표시됩니다.`);
    }

    // 4. 오늘 시트 준비 (초기화 또는 생성)
    let todaySheet = doc.sheetsByTitle[todayStr];
    const headers = ["날짜", "순위", "앱 이름", "개발사(퍼블리셔)", "전일 대비"];
    
    if (todaySheet) {
        await todaySheet.clear();
        await todaySheet.setHeaderRow(headers);
    } else {
        todaySheet = await doc.addSheet({ title: todayStr, headerValues: headers });
    }

    // 5. 구글 플레이스토어 크롤링 (1~100위)
    console.log("플레이스토어 데이터를 가져오는 중...");
    const topGames = await gplay.list({
        category: 'GAME',
        collection: 'TOPGROSSING',
        num: 100,
        country: 'kr',
        lang: 'ko'
    });

    // 6. 데이터 계산 및 추가
    const newRows = [];
    for (let i = 0; i < topGames.length; i++) {
        const game = topGames[i];
        const rank = i + 1;
        const title = game.title;
        const developer = game.developer || '알 수 없음';
        
        let change = 'NEW';
        if (previousRanks[title]) {
            const diff = previousRanks[title] - rank;
            if (diff > 0) change = `▲ ${diff}`;
            else if (diff < 0) change = `▼ ${Math.abs(diff)}`;
            else change = '-';
        }

        newRows.push({
            "날짜": todayStr,
            "순위": rank,
            "앱 이름": title,
            "개발사(퍼블리셔)": developer,
            "전일 대비": change
        });
    }

    if (newRows.length > 0) {
        await todaySheet.addRows(newRows);
        console.log(`${todayStr} 기준 Top 100 업데이트 완료!`);
    } else {
        console.log("업데이트할 데이터가 없습니다.");
    }
}

main().catch(console.error);
