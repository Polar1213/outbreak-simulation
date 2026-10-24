import math
import os
import random as pyRandom
import sys

# RUNTIME SETUP AND WORLD DATA

# Keep CMU Graphics from opening its separate interactive Python console.
os.environ['CI'] = '1'

# Find the bundled CMU Graphics folder so this file can import it.
ROOT = os.path.dirname(os.path.abspath(__file__))
CMU_GRAPHICS_DIR = os.path.join(ROOT, 'cmu_graphics-version-2.0.3')
if CMU_GRAPHICS_DIR not in sys.path:
	sys.path.insert(0, CMU_GRAPHICS_DIR)

from cmu_graphics import *

MAP_ROWS = [
	'NNBRRNCN',
	'NPFLFPRF',
	'RFFFFNNN',
	'HFNFFFNB',
	'RCNRRRBB',
	'RFFFFFRP',
	'NPLFFPCP',
	'NNRRHNBN',
]

# NEW GAME STATE AND INITIALIZATION

def onAppStart(app):
	app.background = 'black'
	app.mode = 'start'
	app.accentColor = 'yellow'
	app.hoverRow = -1
	app.hoverColumn = -1
	app.selectedRow = -1
	app.selectedColumn = -1
	app.selectionAnimation = 0
	app.money = 1000
	app.day = 1
	app.lastDailyIncome = 0
	app.deathCount = 0
	app.recoveryCount = 0
	app.dailyMortalityRate = 0.02
	app.maxDays = 30
	app.businessEarnings = []
	app.businessLevels = []
	app.hospitalCapacities = []
	app.hospitalLevels = []
	app.hospitalPatients = []
	app.hospitalAdmissions = []
	app.blockPopulations = [0] * 64
	app.blockInfections = [0] * 64
	app.newInfectionsToday = [0] * 64
	app.infectionAgeBuckets = [[0, 0, 0, 0] for blockIndex in range(64)]
	app.recoveredInfections = [0] * 64
	app.reportedInfections = []
	app.testedInfections = []
	app.testResultIsCurrent = []
	app.lastTestDay = []
	app.blockVaccinated = []
	app.quarantineDaysRemaining = []
	app.upgradeMessage = ''
	populationShares = []
	totalBasePopulation = 0
	for row in range(8):
		for column in range(8):
			if MAP_ROWS[row][column] == 'N' or MAP_ROWS[row][column] == 'C':
				blockIndex = row * 8 + column
				basePopulation = getBlockPopulation(
					row, column, MAP_ROWS[row][column])
				totalBasePopulation += basePopulation
				populationShares.append((blockIndex, basePopulation))
	allocatedPopulation = 0
	populationRemainders = []
	for blockIndex, basePopulation in populationShares:
		exactPopulation = basePopulation * 50000 / totalBasePopulation
		app.blockPopulations[blockIndex] = int(exactPopulation)
		allocatedPopulation += app.blockPopulations[blockIndex]
		populationRemainders.append((
			exactPopulation - app.blockPopulations[blockIndex], blockIndex))
	populationRemainders.sort(reverse=True)
	for remainderIndex in range(50000 - allocatedPopulation):
		blockIndex = populationRemainders[remainderIndex][1]
		app.blockPopulations[blockIndex] += 1
	initialOutbreakCount = 2
	initialOutbreakBlocks = []
	for row in range(8):
		for column in range(8):
			if MAP_ROWS[row][column] == 'N' or MAP_ROWS[row][column] == 'C':
				initialOutbreakBlocks.append(row * 8 + column)
	pyRandom.shuffle(initialOutbreakBlocks)
	for outbreakNumber in range(initialOutbreakCount):
		blockIndex = initialOutbreakBlocks[outbreakNumber]
		row = blockIndex // 8
		column = blockIndex % 8
		tileType = MAP_ROWS[row][column]
		population = app.blockPopulations[blockIndex]
		app.blockInfections[blockIndex] = int(
			population * pyRandom.randint(1, 3) / 100 + 0.5)
		app.newInfectionsToday[blockIndex] = app.blockInfections[blockIndex]
		app.infectionAgeBuckets[blockIndex][0] = (
			app.blockInfections[blockIndex])
	for row in range(8):
		for column in range(8):
			blockIndex = row * 8 + column
			app.reportedInfections.append(0)
			app.testedInfections.append(-1)
			app.testResultIsCurrent.append(False)
			app.lastTestDay.append(-1)
			if MAP_ROWS[row][column] == 'N' or MAP_ROWS[row][column] == 'C':
				app.blockVaccinated.append(pyRandom.randrange(2))
			else:
				app.blockVaccinated.append(0)
			app.quarantineDaysRemaining.append(0)
			if MAP_ROWS[row][column] == 'B':
				app.businessEarnings.append(125)
				app.businessLevels.append(1)
			else:
				app.businessEarnings.append(0)
				app.businessLevels.append(0)
			if MAP_ROWS[row][column] == 'H':
				app.hospitalCapacities.append(100)
				app.hospitalLevels.append(1)
				app.hospitalPatients.append(0)
			else:
				app.hospitalCapacities.append(0)
				app.hospitalLevels.append(0)
				app.hospitalPatients.append(0)
	admitNewHospitalCases(app)
	updateReportedInfections(app)

# SHARED MAP, DISTRICT, AND ECONOMY HELPERS

def getMapTileSize(app):
	return min((app.height - 130) / 8, (app.width * 0.60) / 8)


def getMapLeft(app):
	return 22


def getMapTop(app):
	return 52


def getTileName(tileType):
	if tileType == 'N':
		return 'Neighborhood'
	if tileType == 'C':
		return 'City'
	if tileType == 'H':
		return 'Hospital'
	if tileType == 'B':
		return 'Business'
	if tileType == 'R':
		return 'Road'
	if tileType == 'L':
		return 'Lake'
	if tileType == 'F':
		return 'Forest'
	return 'Park'


def getTileDescription(tileType):
	if tileType == 'P':
		return 'A lovely public space'
	if tileType == 'F':
		return 'Untamed wilderness'
	if tileType == 'L':
		return 'Scenic and serene wilderness'
	if tileType == 'R':
		return 'Vessel of transmission'
	return ''


def getBusinessEarnings(app, row, column):
	return app.businessEarnings[row * 8 + column]


def getHospitalCapacity(app, row, column):
	return app.hospitalCapacities[row * 8 + column]


def isBlockQuarantined(app, row, column):
	return app.quarantineDaysRemaining[row * 8 + column] > 0


def getBlockPopulation(row, column, tileType):
	if tileType == 'N':
		return 950 + row * 135 + column * 90
	return 5200 + row * 480 + column * 320


def getCurrentBlockPopulation(app, row, column):
	return app.blockPopulations[row * 8 + column]


def hasAdjacentQuarantinedDistrict(app, row, column):
	if row > 0 and (MAP_ROWS[row - 1][column] == 'N' or
					MAP_ROWS[row - 1][column] == 'C'):
		if isBlockQuarantined(app, row - 1, column):
			return True
	if row < 7 and (MAP_ROWS[row + 1][column] == 'N' or
					MAP_ROWS[row + 1][column] == 'C'):
		if isBlockQuarantined(app, row + 1, column):
			return True
	if column > 0 and (MAP_ROWS[row][column - 1] == 'N' or
						MAP_ROWS[row][column - 1] == 'C'):
		if isBlockQuarantined(app, row, column - 1):
			return True
	if column < 7 and (MAP_ROWS[row][column + 1] == 'N' or
						MAP_ROWS[row][column + 1] == 'C'):
		if isBlockQuarantined(app, row, column + 1):
			return True
	return False


def getBusinessDailyIncome(app, row, column):
	dailyIncome = getBusinessEarnings(app, row, column)
	if hasAdjacentQuarantinedDistrict(app, row, column):
		dailyIncome *= 0.5
	return dailyIncome


def formatMoney(amount):
	if amount == int(amount):
		return str(int(amount))
	return '{:.2f}'.format(amount)


def formatPercentage(rate):
	return '{:.2f}'.format(rate * 100).rstrip('0').rstrip('.') + '%'


def formatCounterValue(value):
	if value >= 1000000000:
		formattedValue = '{:.1f}'.format(value / 1000000000)
		if formattedValue.endswith('.0'):
			formattedValue = formattedValue[:-2]
		return formattedValue + 'B'
	if value >= 1000000:
		formattedValue = '{:.1f}'.format(value / 1000000)
		if formattedValue.endswith('.0'):
			formattedValue = formattedValue[:-2]
		return formattedValue + 'M'
	if value >= 10000:
		formattedValue = '{:.1f}'.format(value / 1000)
		if formattedValue.endswith('.0'):
			formattedValue = formattedValue[:-2]
		return formattedValue + 'K'
	return str(value)


def drawCounterLabel(label, centerX, y):
	drawLabel(label, centerX, y, fill='white', align='center', size=10)


def getUpgradeCost(startingCost, currentLevel):
	cost = startingCost
	for levelNumber in range(currentLevel - 1):
		cost *= 2
	return cost


# DAILY SIMULATION AND ECONOMY

def advanceDay(app):
	if app.day < app.maxDays:
		app.day += 1
		advanceInfections(app)
		updateHospitalizationAndMortality(app)
		updateReportedInfections(app)
		for blockIndex in range(64):
			if app.testedInfections[blockIndex] >= 0:
				app.testResultIsCurrent[blockIndex] = False
		app.lastDailyIncome = 0
		for row in range(8):
			for column in range(8):
				if MAP_ROWS[row][column] == 'B':
					app.lastDailyIncome += getBusinessDailyIncome(
						app, row, column)
		app.money += app.lastDailyIncome
		for blockIndex in range(64):
			if app.quarantineDaysRemaining[blockIndex] > 0:
				app.quarantineDaysRemaining[blockIndex] -= 1
		if app.day >= app.maxDays:
			app.mode = 'results'


def updateHospitalizationAndMortality(app):
	admitNewHospitalCases(app)
	hospitalIndices = []
	totalCapacity = 0
	for blockIndex in range(64):
		row = blockIndex // 8
		column = blockIndex % 8
		if MAP_ROWS[row][column] == 'H':
			hospitalIndices.append(blockIndex)
			totalCapacity += app.hospitalCapacities[blockIndex]
	totalPatients = sum(admission[1] for admission in app.hospitalAdmissions)
	occupancy = 0
	if totalCapacity > 0:
		occupancy = totalPatients / totalCapacity
	if occupancy < 0.75:
		app.dailyMortalityRate = 0.02
	elif occupancy < 1.0:
		app.dailyMortalityRate = 0.05
	elif occupancy < 1.25:
		app.dailyMortalityRate = 0.10
	elif occupancy < 1.5:
		app.dailyMortalityRate = 0.20
	else:
		app.dailyMortalityRate = 0.30

	totalActiveInfections = sum(app.blockInfections)
	dailyDeaths = int(totalActiveInfections * app.dailyMortalityRate + 0.5)
	hospitalizedByBlock = [0] * 64
	for admission in app.hospitalAdmissions:
		hospitalizedByBlock[admission[0]] += admission[1]
	for blockIndex in range(64):
		hospitalizedByBlock[blockIndex] = min(
			hospitalizedByBlock[blockIndex], app.blockInfections[blockIndex])
	nonHospitalizedByBlock = [
		app.blockInfections[blockIndex] - hospitalizedByBlock[blockIndex]
		for blockIndex in range(64)]
	totalNonHospitalized = sum(nonHospitalizedByBlock)
	dailyHospitalDeaths = 0
	if totalActiveInfections > 0:
		dailyHospitalDeaths = int(
			dailyDeaths * totalPatients / totalActiveInfections + 0.5)
	dailyHospitalDeaths = min(totalPatients, dailyHospitalDeaths)
	dailyCommunityDeaths = dailyDeaths - dailyHospitalDeaths
	hospitalDeathAllocations = allocateCasesAcrossBlocks(
		[admission[1] for admission in app.hospitalAdmissions],
		dailyHospitalDeaths)
	communityDeathAllocations = allocateCasesAcrossBlocks(
		nonHospitalizedByBlock, dailyCommunityDeaths)
	deathAllocations = [0] * 64
	for admissionIndex, admission in enumerate(app.hospitalAdmissions):
		deaths = hospitalDeathAllocations[admissionIndex]
		admission[1] -= deaths
		deathAllocations[admission[0]] += deaths
	for blockIndex, deaths in enumerate(communityDeathAllocations):
		deathAllocations[blockIndex] += deaths
	for blockIndex, deaths in enumerate(deathAllocations):
		if deaths <= 0:
			continue
		app.blockPopulations[blockIndex] -= deaths
		removeActiveInfections(app, blockIndex, deaths)
		app.deathCount += deaths

	for admission in app.hospitalAdmissions:
		if admission[1] <= 0:
			continue
		admission[2] += 1
		if admission[2] >= 3:
			recoveries = admission[1]
			removeActiveInfections(app, admission[0], recoveries)
			app.recoveredInfections[admission[0]] += recoveries
			app.recoveryCount += recoveries
			admission[1] = 0
	app.hospitalAdmissions = [admission for admission in app.hospitalAdmissions
						  if admission[1] > 0]
	refreshHospitalPatients(app)


def admitNewHospitalCases(app):
	totalNewCases = sum(app.newInfectionsToday)
	newAdmissions = int(totalNewCases * 0.15 + 0.5)
	blockAdmissions = allocateCasesAcrossBlocks(
		app.newInfectionsToday, newAdmissions)
	for blockIndex, admittedCases in enumerate(blockAdmissions):
		if admittedCases > 0:
			app.hospitalAdmissions.append([blockIndex, admittedCases, 0])
	app.newInfectionsToday = [0] * 64
	refreshHospitalPatients(app)


def refreshHospitalPatients(app):
	totalPatients = sum(admission[1] for admission in app.hospitalAdmissions)
	app.hospitalPatients = allocateCasesAcrossBlocks(
		app.hospitalCapacities, totalPatients)


def removeActiveInfections(app, blockIndex, casesToRemove):
	remainingToRemove = casesToRemove
	for ageIndex in range(3, -1, -1):
		removedCases = min(
			remainingToRemove, app.infectionAgeBuckets[blockIndex][ageIndex])
		app.infectionAgeBuckets[blockIndex][ageIndex] -= removedCases
		remainingToRemove -= removedCases
	app.blockInfections[blockIndex] = sum(
		app.infectionAgeBuckets[blockIndex])


def allocateCasesAcrossBlocks(infectionCounts, outcomeCount):
	totalCases = sum(infectionCounts)
	allocations = [0] * len(infectionCounts)
	if totalCases == 0 or outcomeCount == 0:
		return allocations
	remainders = []
	allocated = 0
	for blockIndex, cases in enumerate(infectionCounts):
		exactOutcome = cases * outcomeCount / totalCases
		allocations[blockIndex] = int(exactOutcome)
		allocated += allocations[blockIndex]
		if cases > 0:
			remainders.append((exactOutcome - allocations[blockIndex], blockIndex))
	remainders.sort(reverse=True)
	for remainderIndex in range(outcomeCount - allocated):
		allocations[remainders[remainderIndex][1]] += 1
	return allocations

# INFECTION GROWTH, TRANSMISSION, AND REPORTING

def advanceInfections(app):
	previousInfections = app.blockInfections.copy()
	app.newInfectionsToday = [0] * 64
	updatedInfectionAgeBuckets = [[
		0,
		app.infectionAgeBuckets[blockIndex][0],
		app.infectionAgeBuckets[blockIndex][1],
		app.infectionAgeBuckets[blockIndex][2] +
		app.infectionAgeBuckets[blockIndex][3],
	] for blockIndex in range(64)]
	updatedInfections = [sum(ageBuckets)
					 for ageBuckets in updatedInfectionAgeBuckets]
	susceptibleBlocks = []
	for row in range(8):
		for column in range(8):
			blockIndex = row * 8 + column
			tileType = MAP_ROWS[row][column]
			if tileType != 'N' and tileType != 'C':
				continue

			population = app.blockPopulations[blockIndex]
			susceptible = max(
				0, population - previousInfections[blockIndex] -
				app.recoveredInfections[blockIndex])
			if previousInfections[blockIndex] > 0:
				infectionPercent = previousInfections[blockIndex] / population
				if infectionPercent < 0.05:
					infectionRate = 0.50
				elif infectionPercent < 0.15:
					infectionRate = 0.75
				elif infectionPercent < 0.30:
					infectionRate = 1.0
				else:
					infectionRate = 1.25
				if app.blockVaccinated[blockIndex] == 1:
					infectionRate *= 0.75
				if isBlockQuarantined(app, row, column):
					infectionRate *= 0.5
				newCases = max(
					1, int(previousInfections[blockIndex] *
						  infectionRate + 0.5))
				updatedInfections[blockIndex] = min(
					population - app.recoveredInfections[blockIndex],
					previousInfections[blockIndex] + newCases)
				updatedInfectionAgeBuckets[blockIndex][0] = (
					updatedInfections[blockIndex] - previousInfections[blockIndex])
				app.newInfectionsToday[blockIndex] = (
					updatedInfections[blockIndex] - previousInfections[blockIndex])
				updatedInfectionAgeBuckets[blockIndex][1:] = (
					app.infectionAgeBuckets[blockIndex][:3])
				updatedInfectionAgeBuckets[blockIndex][3] += (
					app.infectionAgeBuckets[blockIndex][3])
				updatedInfections[blockIndex] = sum(
					updatedInfectionAgeBuckets[blockIndex])
			else:
				if susceptible > 0:
					susceptibleBlocks.append(blockIndex)
					spreadChance = getInfectedConnectionChance(
						app, row, column, previousInfections,
						app.blockPopulations)
					if (spreadChance > 0 and
							pyRandom.random() < spreadChance):
						newInfections = min(
							susceptible, pyRandom.randint(25, 75))
						updatedInfections[blockIndex] = newInfections
						updatedInfectionAgeBuckets[blockIndex][0] = (
							newInfections)
						app.newInfectionsToday[blockIndex] = newInfections

	newOutbreakBlocks = [blockIndex for blockIndex in susceptibleBlocks
					 if updatedInfections[blockIndex] == 0]
	if newOutbreakBlocks:
		newOutbreakBlock = pyRandom.choice(newOutbreakBlocks)
		row = newOutbreakBlock // 8
		column = newOutbreakBlock % 8
		population = app.blockPopulations[newOutbreakBlock]
		susceptible = max(0, population - app.recoveredInfections[
			newOutbreakBlock])
		outbreakChance = 0.03
		if app.blockVaccinated[newOutbreakBlock] == 1:
			outbreakChance *= 0.25
		if isBlockQuarantined(app, row, column):
			outbreakChance *= 0.1
		if pyRandom.random() < outbreakChance:
			newInfections = max(
				updatedInfections[newOutbreakBlock], min(
					susceptible, max(1, int(population * 0.01 + 0.5))))
			updatedInfectionAgeBuckets[newOutbreakBlock][0] += (
				newInfections - updatedInfections[newOutbreakBlock])
			app.newInfectionsToday[newOutbreakBlock] += (
				newInfections - updatedInfections[newOutbreakBlock])
			updatedInfections[newOutbreakBlock] = newInfections

	app.blockInfections = updatedInfections
	app.infectionAgeBuckets = updatedInfectionAgeBuckets


def updateReportedInfections(app):
	for blockIndex in range(64):
		trueCases = app.blockInfections[blockIndex]
		if trueCases > 0:
			accuracy = pyRandom.randrange(50, 76) / 100
			app.reportedInfections[blockIndex] = int(
				trueCases * accuracy + 0.5)
		else:
			app.reportedInfections[blockIndex] = 0


def getInfectedConnectionChance(app, row, column, infectionCounts, populations):
	roadQueue = []
	visitedRoads = set()
	spreadChance = 0
	for neighborRow, neighborColumn in getAdjacentCoordinates(row, column):
		neighborType = MAP_ROWS[neighborRow][neighborColumn]
		neighborIndex = neighborRow * 8 + neighborColumn
		if neighborType == 'N' or neighborType == 'C':
			if infectionCounts[neighborIndex] > 0:
				sourceChance = getDistrictSpreadChance(
					infectionCounts[neighborIndex], populations[neighborIndex])
				if app.blockVaccinated[neighborIndex] == 1:
					sourceChance *= 0.5
				if isBlockQuarantined(app, neighborRow, neighborColumn):
					sourceChance *= 0.1
				spreadChance = max(spreadChance, sourceChance)
		elif neighborType == 'R' or neighborType == 'B' or neighborType == 'H':
			roadQueue.append((neighborRow, neighborColumn))
			visitedRoads.add((neighborRow, neighborColumn))

	while roadQueue:
		roadRow, roadColumn = roadQueue.pop(0)
		for neighborRow, neighborColumn in getAdjacentCoordinates(
				roadRow, roadColumn):
			neighborType = MAP_ROWS[neighborRow][neighborColumn]
			neighborIndex = neighborRow * 8 + neighborColumn
			if neighborType == 'N' or neighborType == 'C':
				if infectionCounts[neighborIndex] > 0:
					sourceChance = getDistrictSpreadChance(
						infectionCounts[neighborIndex],
						populations[neighborIndex])
					if app.blockVaccinated[neighborIndex] == 1:
						sourceChance *= 0.5
					if isBlockQuarantined(app, neighborRow, neighborColumn):
						sourceChance *= 0.1
					spreadChance = max(spreadChance, sourceChance)
			elif neighborType == 'R' or neighborType == 'B' or neighborType == 'H':
				roadPosition = (neighborRow, neighborColumn)
				if roadPosition not in visitedRoads:
					visitedRoads.add(roadPosition)
					roadQueue.append(roadPosition)
	targetIndex = row * 8 + column
	if app.blockVaccinated[targetIndex] == 1:
		spreadChance *= 0.25
	if isBlockQuarantined(app, row, column):
		spreadChance *= 0.1
	return spreadChance


def getDistrictSpreadChance(infections, population):
	if population <= 0:
		return 0
	infectionPercent = infections / population
	if infectionPercent < 0.05:
		return 0.30
	if infectionPercent < 0.15:
		return 0.50
	if infectionPercent <= 0.30:
		return 0.75
	return 0.95


def getAdjacentCoordinates(row, column):
	coordinates = []
	if row > 0:
		coordinates.append((row - 1, column))
	if row < 7:
		coordinates.append((row + 1, column))
	if column > 0:
		coordinates.append((row, column - 1))
	if column < 7:
		coordinates.append((row, column + 1))
	return coordinates


# PLAYER INTERVENTIONS: VACCINATION, QUARANTINE, AND TESTING

def vaccinateSelectedBlock(app):
	row = app.selectedRow
	column = app.selectedColumn
	blockIndex = row * 8 + column
	blockType = MAP_ROWS[row][column]
	vaccineCost = getDistrictActionCost(blockType, 750)
	if app.blockVaccinated[blockIndex] == 1:
		app.upgradeMessage = 'This block is already vaccinated'
	elif app.money < vaccineCost:
		app.upgradeMessage = 'Not enough funds ($' + str(vaccineCost) + ' needed)'
	else:
		app.money -= vaccineCost
		app.blockVaccinated[blockIndex] = 1
		app.upgradeMessage = 'Vaccination complete'


def quarantineSelectedBlock(app):
	row = app.selectedRow
	column = app.selectedColumn
	blockIndex = row * 8 + column
	blockType = MAP_ROWS[row][column]
	quarantineCost = getDistrictActionCost(blockType, 500)
	if not canQuarantineDistrict(app, row, column):
		app.upgradeMessage = 'Quarantine unlocks above 25% infected'
	elif app.quarantineDaysRemaining[blockIndex] > 0:
		app.upgradeMessage = 'Wait until quarantine ends before renewing'
	elif app.money < quarantineCost:
		app.upgradeMessage = ('Not enough funds ($' +
							  str(quarantineCost) + ' needed)')
	else:
		app.money -= quarantineCost
		app.quarantineDaysRemaining[blockIndex] = 3
		app.upgradeMessage = 'Quarantine active for 3 game days'


def canQuarantineDistrict(app, row, column):
	blockIndex = row * 8 + column
	population = app.blockPopulations[blockIndex]
	if population <= 0:
		return False
	return app.blockInfections[blockIndex] / population > 0.25


def testSelectedBlock(app):
	row = app.selectedRow
	column = app.selectedColumn
	blockIndex = row * 8 + column
	testCost = getDistrictActionCost(MAP_ROWS[row][column], 250)
	if app.money < testCost:
		app.upgradeMessage = 'Not enough funds ($' + str(testCost) + ' needed)'
	else:
		app.money -= testCost
		app.testedInfections[blockIndex] = app.blockInfections[blockIndex]
		app.testResultIsCurrent[blockIndex] = True
		app.lastTestDay[blockIndex] = app.day
		app.upgradeMessage = 'Test result updated'


def getDistrictActionCost(blockType, neighborhoodCost):
	if blockType == 'C':
		return neighborhoodCost * 2
	return neighborhoodCost


# BUSINESS AND HOSPITAL UPGRADES

def upgradeSelectedBlock(app):
	row = app.selectedRow
	column = app.selectedColumn
	blockIndex = row * 8 + column
	tileType = MAP_ROWS[row][column]

	if tileType == 'B':
		currentLevel = app.businessLevels[blockIndex]
		if currentLevel < 5:
			upgradeCost = getUpgradeCost(150, currentLevel)
			if app.money >= upgradeCost:
				app.money -= upgradeCost
				app.businessEarnings[blockIndex] += 25
				app.businessLevels[blockIndex] += 1
				app.upgradeMessage = ('Income increased by $25 to $' +
					formatMoney(app.businessEarnings[blockIndex]) + '/day')
			else:
				app.upgradeMessage = 'Not enough funds ($' + str(
					upgradeCost) + ' needed)'
	elif tileType == 'H':
		currentLevel = app.hospitalLevels[blockIndex]
		if currentLevel < 5:
			upgradeCost = getUpgradeCost(1000, currentLevel)
			if app.money >= upgradeCost:
				app.money -= upgradeCost
				app.hospitalCapacities[blockIndex] += 100
				app.hospitalLevels[blockIndex] += 1
				app.upgradeMessage = 'Hospital upgraded to level ' + str(
					app.hospitalLevels[blockIndex])
			else:
				app.upgradeMessage = 'Not enough funds ($' + str(
					upgradeCost) + ' needed)'


# INPUT AND NAVIGATION EVENTS

def updateHoveredTile(app, mouseX, mouseY):
	tileSize = getMapTileSize(app)
	mapLeft = getMapLeft(app)
	mapTop = getMapTop(app)
	mapRight = mapLeft + tileSize * 8
	mapBottom = mapTop + tileSize * 8

	if (mapLeft <= mouseX < mapRight and mapTop <= mouseY < mapBottom):
		app.hoverColumn = int((mouseX - mapLeft) / tileSize)
		app.hoverRow = int((mouseY - mapTop) / tileSize)
	else:
		app.hoverRow = -1
		app.hoverColumn = -1


def onMouseMove(app, mouseX, mouseY):
	if app.mode == 'game':
		updateHoveredTile(app, mouseX, mouseY)


def onStep(app):
	if app.selectionAnimation > 0:
		app.selectionAnimation -= 1


def onMousePress(app, mouseX, mouseY):
	if app.mode == 'start':
		buttonY = app.height * 0.66
		playLeft = app.width / 2 - 156
		howToLeft = app.width / 2 + 6

		if (playLeft <= mouseX <= playLeft + 150 and
				buttonY - 24 <= mouseY <= buttonY + 24):
			app.mode = 'game'
		elif (howToLeft <= mouseX <= howToLeft + 150 and
			  buttonY - 24 <= mouseY <= buttonY + 24):
			app.mode = 'howto'
	elif app.mode == 'howto':
		backY = app.height * 0.78
		backLeft = app.width / 2 - 66
		if (backLeft <= mouseX <= backLeft + 132 and
				backY - 24 <= mouseY <= backY + 24):
			app.mode = 'start'
	elif app.mode == 'results':
		menuLeft = app.width / 2 - 100
		menuRight = app.width / 2 + 100
		menuY = app.height * 0.82
		if menuLeft <= mouseX <= menuRight and menuY - 24 <= mouseY <= menuY + 24:
			onAppStart(app)
	elif app.mode == 'game':
		panelLeft = getMapLeft(app) + getMapTileSize(app) * 8 + 18
		nextDayLeft = panelLeft + 14
		nextDayRight = app.width - 22 - 14
		if (nextDayLeft <= mouseX <= nextDayRight and
				115 <= mouseY <= 153):
			advanceDay(app)
			return

		if app.selectedRow >= 0:
			selectedType = MAP_ROWS[app.selectedRow][app.selectedColumn]
			buttonLeft = panelLeft + 14
			buttonRight = app.width - 22 - 14
			if selectedType == 'N' or selectedType == 'C':
				if buttonLeft <= mouseX <= buttonRight and 435 <= mouseY <= 465:
					vaccinateSelectedBlock(app)
					return
				if buttonLeft <= mouseX <= buttonRight and 470 <= mouseY <= 500:
					quarantineSelectedBlock(app)
					return
				if buttonLeft <= mouseX <= buttonRight and 505 <= mouseY <= 535:
					testSelectedBlock(app)
					return
			elif (selectedType == 'B' or selectedType == 'H'):
				if (buttonLeft <= mouseX <= buttonRight and
						430 <= mouseY <= 470):
					upgradeSelectedBlock(app)
					return

		updateHoveredTile(app, mouseX, mouseY)
		if app.hoverRow >= 0:
			tileType = MAP_ROWS[app.hoverRow][app.hoverColumn]
			if (tileType == 'N' or tileType == 'C' or
					tileType == 'H' or tileType == 'B'):
				app.selectedRow = app.hoverRow
				app.selectedColumn = app.hoverColumn
				app.selectionAnimation = 18
				app.upgradeMessage = ''
				return

		backY = app.height * 0.94
		backLeft = app.width / 2 - 66
		if (backLeft <= mouseX <= backLeft + 132 and
				backY - 24 <= mouseY <= backY + 24):
			app.mode = 'start'


def onKeyPress(app, key, modifiers):
	if (key.lower() == 'escape' and
			(app.mode == 'howto' or app.mode == 'game')):
		app.mode = 'start'


# GRAPHICS: MENUS, HELP, AND RESULTS

def drawRadiationLogo(app, centerX, centerY):
	drawCircle(centerX, centerY, 43, fill=app.accentColor)
	for blade in range(3):
		bladeAngle = -90 + blade * 120
		points = []

		for step in range(9):
			angle = bladeAngle - 28 + step * 7
			angleRadians = math.radians(angle)
			points.append(centerX + 36 * math.cos(angleRadians))
			points.append(centerY + 36 * math.sin(angleRadians))

		for step in range(8, -1, -1):
			angle = bladeAngle - 28 + step * 7
			angleRadians = math.radians(angle)
			points.append(centerX + 11 * math.cos(angleRadians))
			points.append(centerY + 11 * math.sin(angleRadians))

		drawPolygon(*points, fill='black')

	drawCircle(centerX, centerY, 8, fill='black')


def drawButton(app, label, button, fill, textColor):
	width = 150
	centerY = app.height * 0.66
	left = app.width / 2 - 156

	if button == 'howto':
		left = app.width / 2 + 6
	elif button == 'back':
		width = 132
		left = app.width / 2 - width / 2
		centerY = app.height * 0.78
	elif button == 'gameback':
		width = 132
		left = app.width / 2 - width / 2
		centerY = app.height * 0.94

	drawRect(left, centerY - 24, width, 48, fill=fill, border=app.accentColor,
			 borderWidth=2)
	drawLabel(label, left + width / 2, centerY, fill=textColor,
			  bold=True, size=16)


def drawStartScreen(app):
	drawLabel('Outbreak', app.width / 2, app.height * 0.22, fill='white',
			  align='center', bold=True, size=68)
	drawRadiationLogo(app, app.width / 2, app.height * 0.45)
	drawButton(app, 'PLAY', 'play', app.accentColor, 'black')
	drawButton(app, 'HOW TO PLAY', 'howto', 'black', app.accentColor)


def drawHowToScreen(app):
	drawLabel('HOW TO PLAY', app.width / 2, 62,
			  fill='white', bold=True, size=30)
	drawLabel('THE SIMULATION', app.width / 2, 113,
			  fill='yellow', bold=True, size=14)
	drawLabel('Each turn is one game day. Press NEXT DAY to advance; the outbreak lasts 30 days.',
			  app.width / 2, 138, fill='white', size=13)
	drawLabel("Infections grow faster as a district's infected share rises and can spread",
			  app.width / 2, 160, fill='white', size=13)
	drawLabel('between connected neighborhoods and cities. Roads, shops, and hospitals',
			  app.width / 2, 179, fill='white', size=13)
	drawLabel('carry spread; lakes, parks, and forests block it.',
			  app.width / 2, 198, fill='white', size=13)
	drawLabel('READ THE MAP', app.width / 2, 237,
			  fill='yellow', bold=True, size=14)
	drawLabel('Select a neighborhood or city to see its population and infection report.',
			  app.width / 2, 261, fill='white', size=13)
	drawLabel('Yellow, orange, and red glows show increasing true infection levels.',
			  app.width / 2, 280, fill='white', size=13)
	drawLabel('Reports are estimates. Test a district to reveal its current true count.',
			  app.width / 2, 299, fill='white', size=13)
	drawLabel('CONTAIN THE OUTBREAK', app.width / 2, 338,
			  fill='yellow', bold=True, size=14)
	drawLabel('Vaccinate districts to slow growth and spread. Quarantine is available',
			  app.width / 2, 362, fill='white', size=13)
	drawLabel('once infection exceeds 25%; it slows transmission but costs funds.',
			  app.width / 2, 381, fill='white', size=13)
	drawLabel('Hospitals admit a share of new cases. Patients stay three days; crowding',
			  app.width / 2, 400, fill='white', size=13)
	drawLabel('raises mortality. Preserve lives and funds to earn a higher final rating.',
			  app.width / 2, 419, fill='white', size=13)
	drawButton(app, 'BACK', 'back', 'black', app.accentColor)


def getFinalRating(deaths):
	if deaths < 1000:
		return 'S', 'Exceptional containment'
	if deaths < 3000:
		return 'A', 'Successful containment'
	if deaths < 6000:
		return 'B', 'Outbreak controlled'
	if deaths < 10000:
		return 'C', 'Heavy losses'
	if deaths < 17500:
		return 'D', 'Severe crisis'
	return 'F', 'Catastrophic failure'


def drawResultsScreen(app):
	rating, outcome = getFinalRating(app.deathCount)
	totalPopulation = 50000
	populationLostPercent = app.deathCount / totalPopulation * 100
	survivors = max(0, totalPopulation - app.deathCount)
	drawLabel('OUTBREAK: FINAL REPORT', app.width / 2, 84,
			  fill='white', bold=True, size=30)
	drawLabel(rating, app.width / 2, 170, fill='yellow',
			  bold=True, size=72)
	drawLabel(outcome, app.width / 2, 228, fill='white',
			  bold=True, size=22)
	drawLabel('Total deaths: ' + formatCounterValue(app.deathCount),
			  app.width / 2, 300, fill='white', size=18)
	drawLabel('Population lost: {:.1f}%'.format(populationLostPercent),
			  app.width / 2, 340, fill='white', size=18)
	drawLabel('Survivors: ' + formatCounterValue(survivors),
			  app.width / 2, 380, fill='white', size=18)
	drawRect(app.width / 2 - 100, app.height * 0.82 - 24, 200, 48,
			 fill='black', border=app.accentColor, borderWidth=2)
	drawLabel('BACK TO MENU', app.width / 2, app.height * 0.82,
			  fill=app.accentColor, bold=True, size=16)


# GRAPHICS: MAP TILE ARTWORK

def drawHouse(x, y, size, houseNumber):
	houseWidth = size * 0.26
	houseHeight = size * 0.27
	if houseNumber == 0:
		houseX = x + size * 0.08
		houseY = y + size * 0.46
	elif houseNumber == 1:
		houseX = x + size * 0.66
		houseY = y + size * 0.46
	else:
		houseX = x + size * 0.37
		houseY = y + size * 0.22

	drawRect(houseX, houseY, houseWidth, houseHeight,
			 fill='ivory', border='saddleBrown', borderWidth=1)
	drawPolygon(houseX - 2, houseY, houseX + houseWidth / 2,
				houseY - size * 0.18, houseX + houseWidth + 2,
				houseY, fill='firebrick')
	drawRect(houseX + houseWidth * 0.42, houseY + houseHeight * 0.55,
			 houseWidth * 0.18, houseHeight * 0.45, fill='saddleBrown')
	drawRect(houseX + houseWidth * 0.12, houseY + houseHeight * 0.20,
			 houseWidth * 0.20, houseHeight * 0.20, fill='lightSkyBlue',
			 border='slateGray', borderWidth=1)
	drawRect(houseX + houseWidth * 0.68, houseY + houseHeight * 0.20,
			 houseWidth * 0.20, houseHeight * 0.20, fill='lightSkyBlue',
			 border='slateGray', borderWidth=1)


def drawNeighborhoodTile(x, y, size):
	drawRect(x, y, size, size, fill='darkSeaGreen', border='darkGreen',
			 borderWidth=1)
	drawHouse(x, y, size, 0)
	drawHouse(x, y, size, 1)
	drawHouse(x, y, size, 2)
	drawCircle(x + size * 0.10, y + size * 0.69, size * 0.045,
			   fill='forestGreen')
	drawCircle(x + size * 0.88, y + size * 0.69, size * 0.045,
			   fill='forestGreen')


def drawTree(x, y, size, treeNumber):
	treeX = x + size * (0.18 + treeNumber * 0.29)
	treeY = y + size * (0.62 - (treeNumber % 2) * 0.12)
	treeSize = size * 0.27

	drawRect(treeX - treeSize * 0.08, treeY, treeSize * 0.16,
			 treeSize * 0.42, fill='saddleBrown')
	drawPolygon(treeX, treeY - treeSize, treeX - treeSize * 0.52,
				treeY + treeSize * 0.28, treeX + treeSize * 0.52,
				treeY + treeSize * 0.28, fill='forestGreen')
	drawPolygon(treeX, treeY - treeSize * 0.62,
				treeX - treeSize * 0.38, treeY + treeSize * 0.04,
				treeX + treeSize * 0.38, treeY + treeSize * 0.04,
				fill='seagreen')


def drawLakeTree(x, y, size, treeNumber):
	treeSize = size * 0.19
	if treeNumber == 0:
		treeX = x + size * 0.11
		treeY = y + size * 0.19
	elif treeNumber == 1:
		treeX = x + size * 0.89
		treeY = y + size * 0.19
	elif treeNumber == 2:
		treeX = x + size * 0.11
		treeY = y + size * 0.78
	else:
		treeX = x + size * 0.89
		treeY = y + size * 0.78

	drawRect(treeX - treeSize * 0.08, treeY, treeSize * 0.16,
			 treeSize * 0.42, fill='saddleBrown')
	drawPolygon(treeX, treeY - treeSize, treeX - treeSize * 0.52,
				treeY + treeSize * 0.28, treeX + treeSize * 0.52,
				treeY + treeSize * 0.28, fill='forestGreen')
	drawPolygon(treeX, treeY - treeSize * 0.62,
				treeX - treeSize * 0.38, treeY + treeSize * 0.04,
				treeX + treeSize * 0.38, treeY + treeSize * 0.04,
				fill='seagreen')


def drawForestTile(x, y, size):
	drawRect(x, y, size, size, fill='darkOliveGreen', border='darkGreen',
			 borderWidth=1)
	for treeNumber in range(3):
		drawTree(x, y, size, treeNumber)


def drawLakeTile(x, y, size):
	drawRect(x, y, size, size, fill='darkOliveGreen', border='darkGreen',
			 borderWidth=1)
	for treeNumber in range(4):
		if treeNumber != 0:
			drawLakeTree(x, y, size, treeNumber)
	lakeWidth = size * 0.50
	lakeHeight = size * 0.38
	lakeX = x + (size - lakeWidth) / 2
	lakeY = y + (size - lakeHeight) / 2
	drawOval(lakeX, lakeY, lakeWidth, lakeHeight,
			 fill='steelBlue', border='tan', borderWidth=2)
	drawOval(x + size * 0.34, y + size * 0.39, size * 0.30,
			 size * 0.08, fill='lightSkyBlue', opacity=75)


def drawParkTile(mapRows, row, column, x, y, size):
	drawRect(x, y, size, size, fill='mediumSeaGreen', border='darkGreen',
			 borderWidth=1)

	if row > 0 and (mapRows[row - 1][column] == 'N' or
					mapRows[row - 1][column] == 'C'):
		drawRect(x + size * 0.43, y, size * 0.14, size * 0.5,
				 fill='tan')
	if row < 7 and (mapRows[row + 1][column] == 'N' or
					mapRows[row + 1][column] == 'C'):
		drawRect(x + size * 0.43, y + size * 0.5, size * 0.14,
				 size * 0.5, fill='tan')
	if column > 0 and (mapRows[row][column - 1] == 'N' or
						mapRows[row][column - 1] == 'C'):
		drawRect(x, y + size * 0.43, size * 0.5, size * 0.14,
				 fill='tan')
	if column < 7 and (mapRows[row][column + 1] == 'N' or
						mapRows[row][column + 1] == 'C'):
		drawRect(x + size * 0.5, y + size * 0.43, size * 0.5,
				 size * 0.14, fill='tan')

	drawTree(x, y, size, 0)
	drawTree(x, y, size, 1)
	drawRect(x + size * 0.69, y + size * 0.67, size * 0.16,
			 size * 0.045, fill='saddlebrown')
	drawRect(x + size * 0.72, y + size * 0.71, size * 0.025,
			 size * 0.08, fill='saddlebrown')
	drawRect(x + size * 0.80, y + size * 0.71, size * 0.025,
			 size * 0.08, fill='saddlebrown')


def drawRoadTile(mapRows, row, column, x, y, size):
	leftType = ''
	rightType = ''
	topType = ''
	bottomType = ''
	if column > 0:
		leftType = mapRows[row][column - 1]
	if column < 7:
		rightType = mapRows[row][column + 1]
	if row > 0:
		topType = mapRows[row - 1][column]
	if row < 7:
		bottomType = mapRows[row + 1][column]

	leftConnects = (leftType == 'R' or leftType == 'N' or
					leftType == 'H' or leftType == 'C' or leftType == 'B')
	rightConnects = (rightType == 'R' or rightType == 'N' or
					 rightType == 'H' or rightType == 'C' or rightType == 'B')
	topConnects = (topType == 'R' or topType == 'N' or topType == 'H' or
				   topType == 'C' or topType == 'B')
	bottomConnects = (bottomType == 'R' or bottomType == 'N' or
					   bottomType == 'H' or bottomType == 'C' or
					   bottomType == 'B')
	connectionCount = 0
	if leftConnects:
		connectionCount += 1
	if rightConnects:
		connectionCount += 1
	if topConnects:
		connectionCount += 1
	if bottomConnects:
		connectionCount += 1

	drawRect(x, y, size, size, fill='darkSeaGreen', border='darkGreen',
			 borderWidth=1)
	roadWidth = size * 0.58
	roadStart = size * 0.21
	roadEnd = size * 0.79
	centerX = x + size / 2
	centerY = y + size / 2

	# Draw the left-edge T junction as one polygon, not overlapping strips.
	if (not leftConnects and rightConnects and topConnects and
			bottomConnects):
		halfRoad = roadWidth / 2
		drawPolygon(centerX - halfRoad, y,
				centerX + halfRoad, y,
				centerX + halfRoad, centerY - halfRoad,
				x + size, centerY - halfRoad,
				x + size, centerY + halfRoad,
				centerX + halfRoad, centerY + halfRoad,
				centerX + halfRoad, y + size,
				centerX - halfRoad, y + size,
				fill='dimGray', border='gainsboro', borderWidth=1)
		drawLine(centerX, y + size * 0.04,
				centerX, centerY - halfRoad * 0.8,
				fill='yellow', lineWidth=1)
		drawLine(centerX + halfRoad * 0.8, centerY,
				x + size * 0.96, centerY, fill='yellow', lineWidth=1)
		drawLine(centerX, centerY + halfRoad * 0.8,
				centerX, y + size * 0.96,
				fill='yellow', lineWidth=1)
		return

	if leftConnects or rightConnects:
		horizontalStart = x
		horizontalEnd = x + size
		if not leftConnects:
			horizontalStart = centerX - roadWidth / 2
		if not rightConnects:
			horizontalEnd = centerX + roadWidth / 2
		drawRect(horizontalStart, y + roadStart,
				 horizontalEnd - horizontalStart, roadWidth, fill='dimGray')
		drawLine(horizontalStart, y + roadStart,
				horizontalEnd, y + roadStart, fill='gainsboro', lineWidth=1)
		drawLine(horizontalStart, y + roadEnd,
				horizontalEnd, y + roadEnd, fill='gainsboro', lineWidth=1)
		drawLine(horizontalStart + size * 0.04, centerY,
				horizontalEnd - size * 0.04, centerY,
				fill='yellow', lineWidth=1)

	if topConnects or bottomConnects:
		verticalStart = y
		verticalEnd = y + size
		if not topConnects:
			verticalStart = centerY - roadWidth / 2
		if not bottomConnects:
			verticalEnd = centerY + roadWidth / 2
		drawRect(x + roadStart, verticalStart, roadWidth,
				 verticalEnd - verticalStart, fill='dimGray')
		drawLine(x + roadStart, verticalStart,
				x + roadStart, verticalEnd, fill='gainsboro', lineWidth=1)
		drawLine(x + roadEnd, verticalStart,
				x + roadEnd, verticalEnd, fill='gainsboro', lineWidth=1)
		drawLine(centerX, verticalStart + size * 0.04,
				centerX, verticalEnd - size * 0.04,
				fill='yellow', lineWidth=1)

	# Use one shared center surface at three-way and four-way junctions.
	if connectionCount >= 3:
		drawCircle(centerX, centerY, roadWidth / 2, fill='dimGray')
		if leftConnects:
			drawLine(x + size * 0.04, centerY,
					centerX - roadWidth * 0.45, centerY,
					fill='yellow', lineWidth=1)
		if rightConnects:
			drawLine(centerX + roadWidth * 0.45, centerY,
					x + size * 0.96, centerY,
					fill='yellow', lineWidth=1)
		if topConnects:
			drawLine(centerX, y + size * 0.04,
					centerX, centerY - roadWidth * 0.45,
					fill='yellow', lineWidth=1)
		if bottomConnects:
			drawLine(centerX, centerY + roadWidth * 0.45,
					centerX, y + size * 0.96,
					fill='yellow', lineWidth=1)


def drawHospitalTile(x, y, size):
	drawRect(x, y, size, size, fill='lightGreen', border='darkGreen',
			 borderWidth=1)
	drawRect(x + size * 0.16, y + size * 0.25, size * 0.68,
			 size * 0.60, fill='white', border='slateGray', borderWidth=1)
	drawRect(x + size * 0.43, y + size * 0.34, size * 0.14,
			 size * 0.40, fill='crimson')
	drawRect(x + size * 0.31, y + size * 0.47, size * 0.38,
			 size * 0.14, fill='crimson')
	drawRect(x + size * 0.45, y + size * 0.68, size * 0.12,
			 size * 0.17, fill='slateGray')


def drawBusinessTile(x, y, size):
	drawRect(x, y, size, size, fill='lightGreen', border='darkGreen',
			 borderWidth=1)
	drawRect(x + size * 0.10, y + size * 0.34, size * 0.80,
			 size * 0.54, fill='peru', border='saddlebrown', borderWidth=1)
	drawRect(x + size * 0.16, y + size * 0.25, size * 0.68,
			 size * 0.15, fill='firebrick')
	for awningStripe in range(4):
		drawRect(x + size * (0.18 + awningStripe * 0.17),
				 y + size * 0.25, size * 0.085, size * 0.15,
				 fill='ivory')
	drawRect(x + size * 0.19, y + size * 0.47, size * 0.26,
			 size * 0.24, fill='lightSkyBlue', border='white', borderWidth=1)
	drawRect(x + size * 0.55, y + size * 0.47, size * 0.26,
			 size * 0.24, fill='lightSkyBlue', border='white', borderWidth=1)
	drawRect(x + size * 0.45, y + size * 0.66, size * 0.12,
			 size * 0.22, fill='saddlebrown')
	drawLabel('SHOP', x + size / 2, y + size * 0.19,
			  fill='white', bold=True, size=max(6, size * 0.16))


def drawCityTile(x, y, size):
	drawRect(x, y, size, size, fill='lightGreen', border='darkGreen',
			 borderWidth=1)
	drawRect(x + size * 0.08, y + size * 0.42, size * 0.25,
			 size * 0.48, fill='steelBlue')
	drawRect(x + size * 0.36, y + size * 0.20, size * 0.28,
			 size * 0.70, fill='darkSlateGray')
	drawRect(x + size * 0.67, y + size * 0.34, size * 0.25,
			 size * 0.56, fill='slateGray')
	for windowRow in range(4):
		for windowColumn in range(3):
			drawRect(x + size * (0.40 + windowColumn * 0.08),
					 y + size * (0.28 + windowRow * 0.13),
					 size * 0.045, size * 0.055, fill='lightSkyBlue')
			drawRect(x + size * 0.75, y + size * (0.43 + windowRow * 0.11),
					 size * 0.08, size * 0.055, fill='lightSkyBlue')
	drawLine(x + size * 0.50, y + size * 0.20,
			x + size * 0.50, y + size * 0.11, fill='darkSlateGray',
			lineWidth=1)


# GRAPHICS: MAP COMPOSITION AND LIVE STATUS PANELS

def drawMapTile(mapRows, row, column, x, y, size):
	tileType = mapRows[row][column]

	if tileType == 'R':
		drawRoadTile(mapRows, row, column, x, y, size)
	elif tileType == 'N':
		drawNeighborhoodTile(x, y, size)
	elif tileType == 'H':
		drawHospitalTile(x, y, size)
	elif tileType == 'B':
		drawBusinessTile(x, y, size)
	elif tileType == 'C':
		drawCityTile(x, y, size)
	elif tileType == 'F':
		drawForestTile(x, y, size)
	elif tileType == 'L':
		drawLakeTile(x, y, size)
	else:
		drawParkTile(mapRows, row, column, x, y, size)


def getInfectionGlowColor(infectionPercent):
	if infectionPercent <= 0:
		return ''
	if infectionPercent < 0.25:
		return 'yellow'
	if infectionPercent < 0.50:
		return 'orange'
	return 'red'


def drawCityMap(app):
	tileSize = getMapTileSize(app)
	mapLeft = getMapLeft(app)
	mapTop = getMapTop(app)

	for row in range(8):
		for column in range(8):
			tileX = mapLeft + column * tileSize
			tileY = mapTop + row * tileSize
			drawMapTile(MAP_ROWS, row, column, tileX, tileY, tileSize)
			infectionCases = app.blockInfections[row * 8 + column]
			blockPopulation = app.blockPopulations[row * 8 + column]
			if infectionCases > 0 and blockPopulation > 0:
				infectionPercent = (infectionCases /
									blockPopulation)
				glowColor = getInfectionGlowColor(infectionPercent)
				if glowColor != '':
					drawRect(tileX - 1, tileY - 1, tileSize + 2,
							 tileSize + 2, fill=None, border=glowColor,
							 borderWidth=8, opacity=18)
					drawRect(tileX, tileY, tileSize, tileSize, fill=None,
							 border=glowColor, borderWidth=4, opacity=40)
					drawRect(tileX, tileY, tileSize, tileSize, fill=None,
							 border=glowColor, borderWidth=2, opacity=90)
			blockIndex = row * 8 + column
			if (MAP_ROWS[row][column] == 'H' and
					app.hospitalPatients[blockIndex] >
					app.hospitalCapacities[blockIndex]):
				drawRect(tileX - 1, tileY - 1, tileSize + 2,
						 tileSize + 2, fill=None, border='red',
						 borderWidth=8, opacity=18)
				drawRect(tileX, tileY, tileSize, tileSize, fill=None,
						 border='red', borderWidth=4, opacity=40)
				drawRect(tileX, tileY, tileSize, tileSize, fill=None,
						 border='red', borderWidth=2, opacity=90)

			if (row == app.selectedRow and
					column == app.selectedColumn):
				drawRect(tileX, tileY, tileSize, tileSize, fill=None,
						 border='yellow', borderWidth=3)
			elif (row == app.hoverRow and column == app.hoverColumn):
				drawRect(tileX, tileY, tileSize, tileSize, fill=None,
						 border='white', borderWidth=2)

	if app.selectionAnimation > 0:
		selectedX = mapLeft + app.selectedColumn * tileSize
		selectedY = mapTop + app.selectedRow * tileSize
		expansion = (18 - app.selectionAnimation) * 0.75
		left = selectedX - expansion
		top = selectedY - expansion
		right = selectedX + tileSize + expansion
		bottom = selectedY + tileSize + expansion
		drawLine(left, top, right, top, fill='yellow', lineWidth=2)
		drawLine(right, top, right, bottom, fill='yellow', lineWidth=2)
		drawLine(right, bottom, left, bottom, fill='yellow', lineWidth=2)
		drawLine(left, bottom, left, top, fill='yellow', lineWidth=2)


def getBlockStats(app, row, column, tileType):
	population = getCurrentBlockPopulation(app, row, column)
	infections = app.blockInfections[row * 8 + column]
	if infections == 0 or population == 0:
		percentInfected = 0
	else:
		percentInfected = int(infections / population * 1000 + 0.5) / 10
	infectionChance = getInfectedConnectionChance(
		app, row, column, app.blockInfections, app.blockPopulations)
	if infectionChance >= 0.25:
		infectionRisk = 'High'
	elif infectionChance >= 0.10:
		infectionRisk = 'Moderate'
	else:
		infectionRisk = 'Low'

	if app.blockVaccinated[row * 8 + column] == 1:
		vaccinationStatus = 'Yes'
	else:
		vaccinationStatus = 'No'

	quarantineDays = app.quarantineDaysRemaining[row * 8 + column]
	if quarantineDays > 0:
		quarantineStatus = 'Active (' + str(quarantineDays) + ' days left)'
	else:
		quarantineStatus = 'Inactive'

	return (population, infections, percentInfected, infectionRisk,
			vaccinationStatus, quarantineStatus)


def drawBlockInfoPanel(app):
	panelLeft = getMapLeft(app) + getMapTileSize(app) * 8 + 18
	panelWidth = app.width - panelLeft - 22
	drawRect(panelLeft, 52, panelWidth, getMapTileSize(app) * 8,
			 fill='gray', opacity=20, border='dimGray', borderWidth=1)
	drawLabel('Funds: $' + formatMoney(app.money), panelLeft + 14, 75,
			  fill='yellow', align='left', bold=True, size=16)
	counterAreaLeft = panelLeft + 14
	counterAreaWidth = panelWidth - 28
	dayWidth = counterAreaWidth * 0.30
	deathWidth = counterAreaWidth * 0.30
	recoveryWidth = counterAreaWidth - dayWidth - deathWidth
	drawCounterLabel(
		'Day: ' + str(app.day) + ' / ' + str(app.maxDays),
		counterAreaLeft + dayWidth / 2, 96)
	drawCounterLabel(
		'Deaths: ' + formatCounterValue(app.deathCount),
		counterAreaLeft + dayWidth + deathWidth / 2, 96)
	drawCounterLabel(
		'Recoveries: ' + formatCounterValue(app.recoveryCount),
		counterAreaLeft + dayWidth + deathWidth + recoveryWidth / 2, 96)
	dayButtonFill = 'yellow'
	dayButtonText = 'black'
	dayButtonLabel = 'NEXT DAY'
	if app.day >= app.maxDays:
		dayButtonFill = 'dimGray'
		dayButtonText = 'white'
		dayButtonLabel = '30 DAYS COMPLETE'
	drawRect(panelLeft + 14, 115, panelWidth - 28, 38,
			 fill=dayButtonFill, border='yellow', borderWidth=2)
	drawLabel(dayButtonLabel, panelLeft + panelWidth / 2, 134,
			  fill=dayButtonText, bold=True, size=13)
	drawLabel('Last payout: $' + formatMoney(app.lastDailyIncome),
			  panelLeft + 14, 187, fill='lightGray', align='left', size=12)

	infoRow = app.hoverRow
	infoColumn = app.hoverColumn
	if infoRow < 0:
		infoRow = app.selectedRow
		infoColumn = app.selectedColumn

	if infoRow < 0:
		drawLabel('BLOCK DETAILS', panelLeft + 14, 210, fill='white',
				  align='left', bold=True, size=18)
		drawLabel('Hover over a map tile', panelLeft + 14, 238,
				  fill='white', align='left', size=13)
		drawLabel('to see its block type.', panelLeft + 14, 258,
				  fill='white', align='left', size=13)
		return

	tileType = MAP_ROWS[infoRow][infoColumn]
	blockName = getTileName(tileType)

	drawLabel(blockName, panelLeft + 14, 210, fill='white',
			  align='left', bold=True, size=22)
	description = getTileDescription(tileType)
	if description != '':
		drawLabel(description, panelLeft + 14, 230, fill='lightGray',
				  align='left', size=12)

	if tileType == 'N' or tileType == 'C':
		population, infections, percentInfected, risk, vaccination, quarantine = (
			getBlockStats(app, infoRow, infoColumn, tileType))
		drawLabel('Population: ' + str(population), panelLeft + 14, 246,
				  fill='white', align='left', size=14)
		blockIndex = infoRow * 8 + infoColumn
		reportedCount = app.reportedInfections[blockIndex]
		reportedPercent = 0
		if population > 0:
			reportedPercent = int(
				reportedCount / population * 1000 + 0.5) / 10
		lastConfirmedCount = app.testedInfections[blockIndex]
		informationY = 271

		if lastConfirmedCount < 0:
			drawLabel('Reported infections: ' + str(reportedCount),
					  panelLeft + 14, informationY,
					  fill='white', align='left', size=14)
			informationY += 21
			drawLabel('Reported infected: ' + str(reportedPercent) + '%',
					  panelLeft + 14, informationY,
					  fill='white', align='left', size=13)
			informationY += 19
			if app.lastTestDay[blockIndex] < 0:
				drawLabel('Not tested yet', panelLeft + 14, informationY,
						  fill='lightGray', align='left', size=10)
			else:
				daysSinceTest = app.day - app.lastTestDay[blockIndex]
				drawLabel('Last tested: ' + str(daysSinceTest) + ' days ago',
						  panelLeft + 14, informationY,
						  fill='lightGray', align='left', size=10)
			informationY += 19
		elif app.testResultIsCurrent[blockIndex]:
			lastConfirmedPercent = 0
			if population > 0:
				lastConfirmedPercent = int(
					lastConfirmedCount / population * 1000 + 0.5) / 10
			drawLabel('True infections: ' + str(lastConfirmedCount),
					  panelLeft + 14, informationY,
					  fill='white', align='left', size=14)
			informationY += 21
			drawLabel('True infected: ' + str(lastConfirmedPercent) + '%',
					  panelLeft + 14, informationY,
					  fill='white', align='left', size=13)
			informationY += 19
		else:
			lastConfirmedPercent = 0
			if population > 0:
				lastConfirmedPercent = int(
					lastConfirmedCount / population * 1000 + 0.5) / 10
			drawLabel('Last confirmed: ' + str(lastConfirmedCount),
				  panelLeft + 14, informationY,
				  fill='white', align='left', size=13)
			informationY += 19
			drawLabel('Last confirmed infected: ' +
				  str(lastConfirmedPercent) + '%',
				  panelLeft + 14, informationY,
				  fill='white', align='left', size=12)
			informationY += 19
			drawLabel('Reported infections: ' + str(reportedCount),
				  panelLeft + 14, informationY,
				  fill='white', align='left', size=13)
			informationY += 19
			drawLabel('Reported infected: ' + str(reportedPercent) + '%',
				  panelLeft + 14, informationY,
				  fill='white', align='left', size=12)
			informationY += 17
		drawLabel('Vaccinated: ' + vaccination,
				  panelLeft + 14, informationY, fill='white', align='left', size=14)
		informationY += 20
		drawLabel('Quarantine: ' + quarantine, panelLeft + 14, informationY,
				  fill='white', align='left', size=14)
		informationY += 18
		drawLabel('Quarantine halves adjacent business income.',
				  panelLeft + 14, informationY,
				  fill='lightGray', align='left', size=9)
	elif tileType == 'B':
		drawLabel('Generates $' + formatMoney(getBusinessDailyIncome(
				app, infoRow, infoColumn)) + ' per day', panelLeft + 14, 246,
				  fill='white', align='left', size=14)
		drawLabel('Each upgrade adds $25 per day.', panelLeft + 14, 274,
				  fill='lightGray', align='left', size=12)
		drawLabel('Select this business to upgrade earnings.',
				  panelLeft + 14, 294,
				  fill='lightGray', align='left', size=12)
	elif tileType == 'H':
		drawLabel('Capacity: ' + str(getHospitalCapacity(
				app, infoRow, infoColumn)) + ' patients', panelLeft + 14, 246,
				  fill='white', align='left', size=14)
		drawLabel('Patients: ' + str(app.hospitalPatients[
				infoRow * 8 + infoColumn]), panelLeft + 14, 274,
				  fill='white', align='left', size=14)
		drawLabel('Daily mortality rate: ' +
				  formatPercentage(app.dailyMortalityRate),
				  panelLeft + 14, 302,
				  fill='white', align='left', size=14)
		drawLabel('Recovery after: 3 hospital days',
				  panelLeft + 14, 328,
				  fill='white', align='left', size=14)
		drawLabel('Each upgrade adds 100 patient capacity.',
				  panelLeft + 14, 354,
				  fill='lightGray', align='left', size=12)
		drawLabel('Select the hospital to upgrade.', panelLeft + 14, 374,
				  fill='lightGray', align='left', size=12)

	selectedType = ''
	selectedIndex = -1
	selectedBlockType = ''
	if app.selectedRow >= 0 and infoRow == app.selectedRow and \
			infoColumn == app.selectedColumn:
		selectedType = MAP_ROWS[infoRow][infoColumn]
		selectedBlockType = selectedType
		selectedIndex = infoRow * 8 + infoColumn
	if selectedType == 'N' or selectedType == 'C':
		vaccineCost = getDistrictActionCost(selectedType, 750)
		if app.blockVaccinated[selectedIndex] == 1:
			vaccineButtonLabel = 'VACCINATED'
			vaccineFill = 'dimGray'
			vaccineText = 'white'
		else:
			vaccineButtonLabel = ('VACCINATE ($' + str(vaccineCost) + ')')
			vaccineFill = 'yellow'
			vaccineText = 'black'
		drawRect(panelLeft + 14, 435, panelWidth - 28, 30,
				 fill=vaccineFill, border='yellow', borderWidth=2)
		drawLabel(vaccineButtonLabel, panelLeft + panelWidth / 2, 450,
				  fill=vaccineText, bold=True, size=12)

		quarantineButtonFill = 'darkOrange'
		quarantineButtonText = 'black'
		quarantineCost = getDistrictActionCost(selectedType, 500)
		quarantineButtonLabel = ('QUARANTINE 3 DAYS ($' +
								  str(quarantineCost) + ')')
		quarantineDays = app.quarantineDaysRemaining[selectedIndex]
		if quarantineDays > 0:
			quarantineButtonFill = 'dimGray'
			quarantineButtonText = 'white'
			quarantineButtonLabel = ('QUARANTINED: ' +
								  str(quarantineDays) + ' DAYS LEFT')
		elif not canQuarantineDistrict(app, app.selectedRow,
										 app.selectedColumn):
			quarantineButtonFill = 'dimGray'
			quarantineButtonText = 'white'
			quarantineButtonLabel = 'LOCKED: >25% INFECTED'
		drawRect(panelLeft + 14, 470, panelWidth - 28, 30,
				 fill=quarantineButtonFill, border='yellow', borderWidth=2)
		drawLabel(quarantineButtonLabel, panelLeft + panelWidth / 2, 485,
				  fill=quarantineButtonText, bold=True, size=11)
		testCost = getDistrictActionCost(selectedType, 250)
		testButtonLabel = 'TEST INFECTIONS ($' + str(testCost) + ')'
		if app.testedInfections[selectedIndex] >= 0:
			testButtonLabel = 'RETEST INFECTIONS ($' + str(testCost) + ')'
		drawRect(panelLeft + 14, 505, panelWidth - 28, 30,
				 fill='lightSkyBlue', border='white', borderWidth=2)
		drawLabel(testButtonLabel,
			  panelLeft + panelWidth / 2, 520,
			  fill='black', bold=True, size=11)
		if app.lastTestDay[selectedIndex] < 0:
			testStatus = 'Not tested yet'
		else:
			daysSinceTest = app.day - app.lastTestDay[selectedIndex]
			testStatus = 'Last tested: ' + str(daysSinceTest) + ' days ago'
		if app.testResultIsCurrent[selectedIndex]:
			testStatus = 'Last tested today'
		drawLabel(testStatus, panelLeft + 14, 548,
			  fill='lightGray', align='left', size=10)
		if app.upgradeMessage != '':
			drawLabel(app.upgradeMessage, panelLeft + 14, 568,
				  fill='white', align='left', size=10)
	elif selectedType == 'B' or selectedType == 'H':
		buttonFill = 'yellow'
		buttonText = 'black'
		if selectedType == 'B':
			currentLevel = app.businessLevels[selectedIndex]
			if currentLevel < 5:
				upgradeCost = getUpgradeCost(150, currentLevel)
				buttonLabel = ('UPGRADE: +$25/DAY ($' +
							  str(upgradeCost) + ')')
			else:
				buttonLabel = 'MAX LEVEL 5'
				buttonFill = 'dimGray'
				buttonText = 'white'
		else:
			currentLevel = app.hospitalLevels[selectedIndex]
			if currentLevel < 5:
				upgradeCost = getUpgradeCost(1000, currentLevel)
				buttonLabel = ('UPGRADE: ' + str(currentLevel) + ' > ' +
							  str(currentLevel + 1) + ' ($' +
							  str(upgradeCost) + ')')
			else:
				buttonLabel = 'MAX LEVEL 5'
				buttonFill = 'dimGray'
				buttonText = 'white'
		drawRect(panelLeft + 14, 430, panelWidth - 28, 40,
				 fill=buttonFill, border='yellow', borderWidth=2)
		drawLabel(buttonLabel, panelLeft + panelWidth / 2, 450,
				  fill=buttonText, bold=True, size=11)
		if app.upgradeMessage != '':
			drawLabel(app.upgradeMessage, panelLeft + 14, 492,
					  fill='white', align='left', size=11)


# GRAPHICS: GAME SCREEN AND APP RENDERING

def drawGameScreen(app):
	drawLabel('OUTBREAK SIMULATION', getMapLeft(app) +
			  getMapTileSize(app) * 4, 24,
			  fill='white', bold=True, size=18)
	drawCityMap(app)
	drawBlockInfoPanel(app)
	drawButton(app, 'BACK', 'gameback', 'black', app.accentColor)


def redrawAll(app):
	drawRect(0, 0, app.width, app.height, fill='black', align='top-left')

	if app.mode == 'start':
		drawStartScreen(app)
	elif app.mode == 'howto':
		drawHowToScreen(app)
	elif app.mode == 'results':
		drawResultsScreen(app)
	else:
		drawGameScreen(app)


# APPLICATION ENTRY POINT

runApp(width=800, height=600)
