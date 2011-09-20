
fileName = args[0]
symbol = args[1]

interpreteR = R('arimaAdaptor.r')

TimeZone.setDefault(TimeZone.getTimeZone("GMT+10"))

noAccumulator = ZeroAccumulator()
lineProcessor = ReutersCSVLineParser(fileName)
source = SingleSymbolScanner(fileName, symbol, lineProcessor, noAccumulator)
cache = RandomAccessCache(5000)
lineProcessor.addCacheWriteable(cache)

MIN_MC_MINUTE = 540
MAX_MC_MINUTE = 1049
#
# Stores for each instrument and minute in day, the list of %volumes/dailyVol 
# for each minute.
#
class TraversalCutter(Listener):

    def __init__(self):
        self.data = HashMap()   # minute of day -> list of values
        self.days = HashMap()   # minute of day -> list of available dates
        self.seqOfDays = []     # list of days


    def notify(self, parseResult):
        moment = parseResult.getTimestamp()
        minute = moment.get(Calendar.HOUR_OF_DAY)*60 \
                + moment.get(Calendar.MINUTE)

        minute = minute + 60*cache.get(moment, \
                Field.EXTENDED(Field.Qualifier.NONE, "GMT"), symbol)
        minute = int(minute)

        if minute>=MIN_MC_MINUTE and minute<=MAX_MC_MINUTE:
            if self.data.get(minute)==None: 
                self.data.put(minute, [])
                self.days.put(minute, [])

            dayAndMonth = str(moment.get(Calendar.DAY_OF_MONTH)) \
                        + "-" + str(moment.get(Calendar.MONTH)+1)
            try:
                self.data.get(minute).append(cache.get(moment, \
                        Field.VOLUME(), symbol))
                self.days.get(minute).append(dayAndMonth)

                if len(self.seqOfDays)==0 or self.seqOfDays[-1]!=dayAndMonth:
                    self.seqOfDays.append(dayAndMonth)
            except:
                None




        # The same as:
        #data[minute].push(parseResult.values(symbol).get(VOLUME()))


    ##
    ## Calculates percent values for volume over the daily traded volume.
    ##
    def calculatePercents(self):
        for day in self.seqOfDays:
            dailyVol = 0
            for m in range(MIN_MC_MINUTE, MAX_MC_MINUTE+1):
                if self.days.get(m)==None: continue
                for i in range(0, len(self.days.get(m))):
                    if self.days.get(m)[i]==day:
                        dailyVol = dailyVol + self.data.get(m)[i]
                        break

            for m in range(MIN_MC_MINUTE, MAX_MC_MINUTE+1):
                if self.days.get(m)==None: continue
                for i in range(0, len(self.days.get(m))):
                    if self.days.get(m)[i]==day:
                        self.data.get(m)[i] = self.data.get(m)[i] / dailyVol
                        break
                


    ##
    ## Forecasts proportional volatilities for each minute of day
    ##
    ## Returns a list of values for each minute of day.
    ##
    def forecast(self, p, d, q):
        result = []
        interpreteR.eval('predictor <- arimaPredictor(' + str(p) + ',' + \
                str(d) + ',' + str(q) + ')')
        for m in range(0,MIN_MC_MINUTE): result.append(0)

        for m in range(MIN_MC_MINUTE, MAX_MC_MINUTE+1):
            if self.days.get(m)==None: continue
            interpreteR.eval('predictor$clean()')
    
            for i in range(0, len(self.days.get(m))):
                 interpreteR.eval('predictor$learn(' \
                        + str(self.data.get(m)[i]) + ')')
                
            interpreteR.eval('x<-predictor$forecast()')
            predictedVol = interpreteR.evalDouble('x')
            result.append(predictedVol)

        for m in range(MAX_MC_MINUTE+1,60*24): result.append(0)

        return result


traversalCutter = TraversalCutter()
noAccumulator.addListener(traversalCutter)

# Collect data
source.run()

# Transform data
traversalCutter.calculatePercents()

# Predict using ARIMA
forecastedVol=traversalCutter.forecast(1,0,1)
print forecastedVol
interpreteR.end()

