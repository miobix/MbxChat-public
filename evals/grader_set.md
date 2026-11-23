# Grader set (labeled data: written for the purpose, proofread by the user)

Learner answers with known errors, used to score grading models (SPEC §9, unit 6b). Nothing here
comes from real practice data.

## How to proofread

Each item ends with a `check:` line. Write one of:
- `check: ok` (the item is right as written)
- `check: fix <what to change>` (e.g. `check: fix verdict minor`, `check: fix errors 가 → 를 only`)
- `check: drop` (ambiguous or unnatural; leave it out)

Anything after the keyword is free text. Unchecked items are not used by the eval.

## Verdict rubric

- **correct**: no errors. Other natural phrasings of the reference are correct too.
- **minor**: the meaning comes through; small slips (spacing, spelling, one particle, a slightly
  off word, an honorific slip that is impolite but clear).
- **wrong**: the meaning changes or is lost, the grammar is broken, the register is wrong for
  the situation (반말 to a boss or customer), or the required grammar is not used.

## Correct answers (false-alarm check)

### g01 · correct
- task: translate
- prompt: I'm heading to the store now. Need anything?
- situation: to a friend
- reference: 지금 마트 가는데 뭐 필요한 거 있어?
- answer: 지금 마트 가는 길인데 필요한 거 있어?
- errors: none
- verdict: correct
- check: ok

### g02 · correct
- task: translate
- prompt: The meeting ran long. Did you get to eat lunch?
- situation: to a coworker
- reference: 회의가 길어졌는데 점심은 드셨어요?
- answer: 회의가 길어졌는데 점심 드셨어요?
- errors: none
- verdict: correct
- check: ok

### g03 · correct
- task: translate
- prompt: Could you send me the file again?
- situation: to a coworker
- answer: 파일 다시 보내 주실 수 있어요?
- errors: none
- verdict: correct
- check: ok 

### g04 · correct
- task: translate
- prompt: I forgot my umbrella, so I got soaked.
- situation: to a friend
- answer: 우산을 깜빡해서 비를 쫄딱 맞았어.
- errors: none
- verdict: correct
- check: ok 

### g05 · correct
- task: translate
- prompt: It's been a while! How have you been?
- situation: to a friend
- answer: 오랜만이야! 잘 지냈어?
- errors: none
- verdict: correct
- check: ok

### g06 · correct
- task: translate
- prompt: I'll be about ten minutes late.
- situation: to my boss
- answer: 10분 정도 늦을 것 같습니다.
- errors: none
- verdict: correct
- check: ok

### g07 · correct
- task: grammar
- prompt: -는데
- word: 피곤하다 (to be tired)
- answer: 피곤한데 오늘은 일찍 잘게요.
- errors: none
- verdict: correct
- check: ok

### g08 · correct
- task: grammar
- prompt: -아/어서
- word: 바쁘다 (to be busy)
- answer: 요즘 너무 바빠서 운동을 못 했어요.
- errors: none
- verdict: correct
- check: ok

### g09 · correct
- task: grammar
- prompt: -(으)면서
- word: 듣다 (to listen)
- answer: 음악을 들으면서 공부해요.
- errors: none
- verdict: correct
- check: ok 

### g10 · correct
- task: grammar
- prompt: -기 때문에
- word: 비싸다 (to be expensive)
- answer: 너무 비싸기 때문에 안 샀어요.
- errors: none
- verdict: correct
- check: ok

### g11 · correct
- task: grammar
- prompt: -(으)ㄹ 수 있다
- word: 운전하다 (to drive)
- answer: 저는 운전할 수 있어요.
- errors: none
- verdict: correct
- check: ok

### g12 · correct
- task: grammar
- prompt: -게 되다
- word: 이사하다 (to move house)
- answer: 다음 달에 부산으로 이사하게 됐어요.
- errors: none
- verdict: correct
- check: ok 

### g13 · correct
- task: grammar
- prompt: -는 바람에
- word: 늦잠 (oversleeping)
- answer: 늦잠을 자는 바람에 버스를 놓쳤어요.
- errors: none
- verdict: correct
- check: ok

### g14 · correct
- task: translate
- prompt: Let's grab a coffee after work.
- situation: to a friend
- answer: 퇴근하고 커피 한잔하자.
- errors: none
- verdict: correct
- check: ok

### g15 · correct
- task: translate
- prompt: Thank you for your help yesterday.
- situation: to a senior colleague
- answer: 어제 도와주셔서 감사합니다.
- errors: none
- verdict: correct
- check: ok

### g16 · correct
- task: grammar
- prompt: -더라고요
- word: 맛있다 (to be tasty)
- answer: 그 식당 생각보다 맛있더라고요.
- errors: none
- verdict: correct
- check: ok

### g17 · correct
- task: grammar
- prompt: -(으)ㄹ 수 있다
- word: 수영하다 (to swim)
- answer: 저는 수영할 수 없어요.
- errors: none
- verdict: correct
- check: ok

### g18 · correct
- task: grammar
- prompt: -거든요
- word: 바쁘다 (to be busy)
- answer: 내일은 못 가요. 일이 좀 바쁘거든요.
- errors: none
- verdict: correct
- check: ok

## Spacing and spelling

### g19 · spacing
- task: translate
- prompt: I'll go home and rest.
- situation: to a friend
- answer: 집에가서 쉴거야.
- errors: 집에가서 → 집에 가서: spacing; 쉴거야 → 쉴 거야: spacing before 거
- verdict: minor
- check: ok

### g20 · spelling
- task: translate
- prompt: I didn't know that.
- situation: to a friend
- answer: 그거 몰랏어.
- errors: 몰랏어 → 몰랐어: past tense is ㅆ
- verdict: minor
- check: ok

### g21 · spelling
- task: translate
- prompt: Please wait a moment.
- situation: to a customer
- answer: 잠시만 기달려 주세요.
- errors: 기달려 → 기다려: the verb is 기다리다
- verdict: minor
- check: ok 

### g22 · spelling
- task: grammar
- prompt: -는데
- word: 비가 오다 (to rain)
- answer: 밖에 비가 오는대 우산 있어요?
- errors: 오는대 → 오는데: the ending is spelled -는데
- verdict: minor
- check: ok 

### g23 · spelling
- task: translate
- prompt: It's okay, don't worry.
- situation: to a coworker
- answer: 괜찬아요, 걱정하지 마세요.
- errors: 괜찬아요 → 괜찮아요: spelling
- verdict: minor
- check: ok 

### g24 · spelling
- task: translate
- prompt: See you tomorrow.
- situation: to a coworker
- answer: 내일 뵈요.
- errors: 뵈요 → 봬요: 봬요 is the contraction of 뵈어요
- verdict: minor
- check: ok
 
### g25 · spacing
- task: grammar
- prompt: -(으)ㄹ 것 같다
- word: 늦다 (to be late)
- answer: 오늘 좀 늦을것 같아요.
- errors: 늦을것 → 늦을 것: spacing before 것
- verdict: minor
- check: ok

### g26 · spacing
- task: translate
- prompt: I want to go there someday.
- situation: to a coworker
- answer: 언젠가 거기 가고싶어요.
- errors: 가고싶어요 → 가고 싶어요: spacing before 싶다
- verdict: minor
- check: ok

## Particles

### g27 · particle
- task: translate
- prompt: I like spicy food.
- situation: to a coworker
- reference: 저는 매운 음식을 좋아해요.
- answer: 저는 매운 음식이 좋아해요.
- errors: 음식이 → 음식을: 좋아하다 takes an object (or keep 이 with 좋아요)
- verdict: minor
- check: ok

### g28 · particle
- task: translate
- prompt: I met my friend at the café.
- situation: to a coworker
- answer: 카페에 친구를 만났어요.
- errors: 카페에 → 카페에서: where an action happens takes 에서
- verdict: minor
- check: ok

### g29 · particle
- task: translate
- prompt: I go to work by subway.
- situation: to a coworker
- answer: 지하철을 회사에 가요.
- errors: 지하철을 → 지하철로: means of transport takes (으)로
- verdict: minor
- check: ok

### g30 · particle
- task: translate
- prompt: My younger brother is taller than me.
- situation: to a friend
- answer: 남동생이 나만큼 키가 커.
- errors: 나만큼 → 나보다: 만큼 means "as tall as", not "taller than"
- verdict: wrong
- check: ok 

### g31 · particle
- task: translate
- prompt: I gave my mom a present.
- situation: to a friend
- answer: 엄마를 선물을 줬어.
- errors: 엄마를 → 엄마한테: the receiver takes 한테/에게
- verdict: minor
- check: ok

### g32 · particle
- task: translate
- prompt: I'm interested in Korean history.
- situation: to a coworker
- answer: 한국 역사를 관심이 있어요.
- errors: 역사를 → 역사에: 관심이 있다 takes 에
- verdict: minor
- check: ok

### g33 · particle
- task: grammar
- prompt: -기로 하다
- word: 만나다 (to meet)
- answer: 우리 토요일에 만나기를 했어요.
- errors: 만나기를 했어요 → 만나기로 했어요: the pattern is -기로 하다
- verdict: wrong
- check: ok

### g34 · particle
- task: translate
- prompt: Only I know.
- situation: to a friend
- answer: 나도 알아.
- errors: 나도 → 나만: 도 means "me too", 만 means "only me"
- verdict: wrong
- check: ok

## Verb voice, tense and form

### g35 · voice
- task: grammar
- prompt: -는데
- word: 연기하다 (to postpone)
- answer: 회의가 연기했는데 몰랐어요.
- errors: 연기했는데 → 연기됐는데: the meeting is postponed, so the passive 연기되다
- verdict: wrong
- check: ok

### g36 · voice
- task: translate
- prompt: The door opened by itself.
- situation: to a friend
- answer: 문이 저절로 열었어.
- errors: 열었어 → 열렸어: with the door as subject the verb is 열리다
- verdict: wrong
- check: ok

### g37 · voice
- task: translate
- prompt: My phone screen broke.
- situation: to a friend
- answer: 핸드폰 화면이 깼어.
- errors: 깼어 → 깨졌어: with the screen as subject the verb is 깨지다
- verdict: wrong
- check: ok

### g38 · voice
- task: translate
- prompt: I got bitten by a mosquito.
- situation: to a friend
- answer: 모기가 물렸어.
- errors: 모기가 → 모기한테: as written, the mosquito got bitten
- verdict: wrong
- check: ok

### g39 · tense
- task: translate
- prompt: I'm going to Busan next week.
- situation: to a coworker
- answer: 다음 주에 부산에 갔어요.
- errors: 갔어요 → 갈 거예요: past tense for a future plan
- verdict: wrong
- check: ok

### g40 · form
- task: grammar
- prompt: -는데
- word: 춥다 (to be cold)
- answer: 날씨가 춥는데 어디 가요?
- errors: 춥는데 → 추운데: descriptive verbs take -(으)ㄴ데
- verdict: minor
- check: ok

### g41 · form
- task: translate
- prompt: I helped my friend move.
- situation: to a coworker
- answer: 친구 이사를 돕았어요.
- errors: 돕았어요 → 도왔어요: 돕다 is ㅂ-irregular
- verdict: minor
- check: ok

## Register and honorifics

### g42 · register
- task: translate
- prompt: Have you eaten?
- situation: to my boss
- answer: 밥 먹었어?
- errors: 밥 먹었어 → 식사하셨어요: 반말 to a boss
- verdict: wrong
- check: ok

### g43 · register
- task: translate
- prompt: The meeting got pushed to next week.
- situation: to my boss
- reference: 회의가 다음 주로 미뤄졌어요.
- answer: 회의 다음 주로 미뤄졌어.
- errors: 미뤄졌어 → 미뤄졌어요: 반말 to a boss; 회의 → 회의가: subject particle dropped
- verdict: wrong
- check: ok

### g44 · honorific
- task: translate
- prompt: My grandmother is sleeping.
- situation: to a coworker
- answer: 할머니가 자고 있어요.
- errors: 할머니가 자고 있어요 → 할머니께서 주무시고 계세요: honorific verbs for a grandparent
- verdict: minor
- check: ok

### g45 · register
- task: translate
- prompt: What's your name?
- situation: to a customer at work
- answer: 이름이 뭐야?
- errors: 이름이 뭐야 → 성함이 어떻게 되세요: 반말 to a customer
- verdict: wrong
- check: ok

### g46 · register
- task: translate
- prompt: Are you coming tonight?
- situation: to a close friend
- answer: 오늘 밤에 오십니까?
- errors: 오십니까 → 와: formal honorific to a close friend sounds cold
- verdict: minor
- check: ok

### g47 · honorific
- task: translate
- prompt: The teacher said so.
- situation: to a coworker
- answer: 선생님이 그렇게 말했어요.
- errors: 말했어요 → 말씀하셨어요: honorific for a teacher
- verdict: minor
- check: ok

### g48 · honorific
- task: translate
- prompt: I'll call you later.
- situation: to my boss
- answer: 제가 나중에 전화하시겠습니다.
- errors: 전화하시겠습니다 → 전화드리겠습니다: never use -시- for yourself
- verdict: minor
- check: ok

### g49 · honorific
- task: translate
- prompt: Please eat a lot.
- situation: to older guests
- answer: 많이 먹어요.
- errors: 먹어요 → 드세요: 드시다 for elders
- verdict: minor
- check: ok

## Connectives and the required grammar

### g50 · connective
- task: grammar
- prompt: -아/어서
- word: 비가 오다 (to rain)
- answer: 비가 와서 우산을 가져가세요.
- errors: 와서 → 오니까: -아/어서 cannot lead into a command; use -(으)니까
- verdict: minor
- check: ok

### g51 · connective
- task: grammar
- prompt: -(으)면서
- word: 먹다 (to eat)
- answer: 밥을 먹으면서 친구가 TV를 봐요.
- errors: -(으)면서 needs one subject for both actions → 저는 밥을 먹으면서 TV를 봐요
- verdict: wrong
- check: ok

### g52 · connective
- task: grammar
- prompt: -는 바람에
- word: 비가 오다 (to rain)
- answer: 비가 오는 바람에 소풍이 즐거웠어요.
- errors: -는 바람에 gives the cause of an unwanted result → 소풍이 취소됐어요
- verdict: wrong
- check: ok

### g53 · missing grammar
- task: grammar
- prompt: -게 되다
- word: 알다 (to know)
- answer: 그 사람을 작년에 알았어요.
- errors: -게 되다 not used → 그 사람을 작년에 알게 됐어요
- verdict: wrong
- check: ok

### g54 · missing grammar
- task: grammar
- prompt: -기 때문에
- word: 아프다 (to be sick)
- answer: 아파서 학교에 안 갔어요.
- errors: -기 때문에 not used (the sentence itself is fine) → 아프기 때문에 학교에 안 갔어요
- verdict: wrong
- check: ok

## Word choice and collocations

### g55 · collocation
- task: translate
- prompt: I'm going to take a shower.
- situation: to a friend
- answer: 샤워를 받을게.
- errors: 샤워를 받을게 → 샤워할게: the verb is 샤워하다
- verdict: minor
- check: ok

### g56 · collocation
- task: translate
- prompt: I caught a cold.
- situation: to a coworker
- answer: 감기를 잡았어요.
- errors: 감기를 잡았어요 → 감기에 걸렸어요: 감기에 걸리다; 잡다 does not carry the meaning
- verdict: wrong
- check: ok

### g57 · collocation
- task: translate
- prompt: Please make a reservation for two.
- situation: to restaurant staff
- answer: 두 명 예약을 만들어 주세요.
- errors: 예약을 만들어 주세요 → 예약해 주세요: the verb is 예약하다
- verdict: minor
- check: ok

### g58 · word choice
- task: translate
- prompt: I've got all the materials ready.
- situation: to my boss
- answer: 재료를 다 준비했습니다.
- errors: 재료 → 자료: 재료 is ingredients or raw material, 자료 is documents
- verdict: minor
- check: ok

### g59 · collocation
- task: translate
- prompt: I lost weight.
- situation: to a friend
- answer: 몸무게를 잃었어.
- errors: 몸무게를 잃었어 → 살이 빠졌어: 잃다 does not go with weight
- verdict: minor
- check: ok

### g60 · collocation
- task: translate
- prompt: Turn on the light.
- situation: to a friend
- answer: 불 열어 줘.
- errors: 열어 → 켜: lights are 켜다
- verdict: minor
- check: ok

### g61 · collocation
- task: translate
- prompt: Wear a hat, it's sunny.
- situation: to a friend
- answer: 햇빛이 강하니까 모자 입어.
- errors: 입어 → 써: hats are 쓰다
- verdict: minor
- check: ok

### g62 · collocation
- task: translate
- prompt: I made a mistake.
- situation: to a coworker
- answer: 제가 실수를 만들었어요.
- errors: 실수를 만들었어요 → 실수했어요: the verb is 실수하다
- verdict: minor
- check: ok

## Several errors at once

### g63 · mixed
- task: translate
- prompt: I was so tired yesterday that I went to bed early.
- situation: to a friend
- answer: 어제 너무 피곤했어서 일찍 잣어.
- errors: 피곤했어서 → 피곤해서: no past tense before -아서; 잣어 → 잤어: spelling
- verdict: minor
- check: ok

### g64 · mixed
- task: translate
- prompt: The weather is nice, so let's go for a walk.
- situation: to a friend
- answer: 날씨가 좋아서 산책하러 가자.
- errors: 좋아서 → 좋으니까: -아/어서 cannot lead into a suggestion
- verdict: minor
- check: ok

### g65 · mixed
- task: translate
- prompt: I couldn't finish the report because I was sick.
- situation: to my boss
- answer: 아파서 보고서를 끝나지 못했어.
- errors: 끝나지 → 끝내지 (or 마무리하지): finishing something is 끝내다; 못했어 → 못했습니다 (or 못했어요): 반말 to a boss
- verdict: wrong
- check: ok

### g66 · mixed
- task: translate
- prompt: I'm looking for a gift for my mom.
- situation: to a shop clerk
- answer: 엄마 선물을 찿고 있어요.
- errors: 찿고 → 찾고: spelling
- verdict: minor
- check: ok
